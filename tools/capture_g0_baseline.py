#!/usr/bin/env python3
"""Capture reproducible G0 screenshots from an unchanged YTB baseline runtime.

The script creates only synthetic records in the disposable API database supplied
by the caller.  It never edits application source or a user database.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, sync_playwright

AUDITED_BASELINE = "b35834808d99067e362a6e728ce7af8e04d2b6bd"
FIXTURE_NAME = "C0 G0 Synthetic Channel"
PROJECT_NAME = "C0 G0 Synthetic Project"


def api_json(base_url: str, path: str, method: str = "GET", body: object | None = None) -> Any:
    payload = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=payload,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} failed with HTTP {exc.code}: {detail}") from exc


def fixture_dna() -> dict[str, Any]:
    hold = lambda minimum, maximum: {"preferred_hold_seconds": {"min": minimum, "max": maximum}}
    return {
        "schema_version": "3.0",
        "channel": {
            "name": FIXTURE_NAME,
            "language": "English",
            "niche": "2D animation production",
            "audience": "Independent animation teams",
        },
        "narration_wpm": {"min": 130, "max": 165},
        "pacing_profiles": {
            "fast": {"high": hold(0.4, 0.8), "medium": hold(0.8, 1.2), "low": hold(1.2, 1.8)},
            "medium": {"high": hold(0.8, 1.2), "medium": hold(1.2, 1.8), "low": hold(1.8, 2.5)},
            "slow": {"high": hold(1.2, 1.8), "medium": hold(1.8, 2.6), "low": hold(2.6, 3.8)},
        },
        "narration_identity": {
            "voice": ["clear", "warm"],
            "delivery": ["measured"],
            "explanation_style": ["visual examples"],
            "tone_boundaries": ["practical"],
            "avoid": ["hype"],
        },
        "visual_identity": {
            "medium": ["2D vector animation"],
            "linework": ["clean outlines"],
            "rendering": ["flat shading"],
            "palette": ["navy and cyan"],
            "shape_language": ["rounded geometric forms"],
            "texture": ["subtle grain"],
            "editorial_language": ["clear visual hierarchy"],
        },
        "entity_styles": {
            "character": {"appearance": ["expressive silhouettes"], "avoid": ["photorealism"]},
            "location": {"appearance": ["layered stages"], "avoid": ["visual clutter"]},
            "prop": {"appearance": ["readable icons"], "avoid": ["tiny details"]},
            "recurring_visual_subject": {"appearance": ["cyan accent"], "avoid": ["inconsistent scale"]},
        },
        "global_negative_constraints": ["No copyrighted characters", "No production secrets"],
    }


def seed_disposable_data(api_url: str) -> tuple[dict[str, Any], dict[str, Any]]:
    channels = api_json(api_url, "/api/v3/channels")["items"]
    channel = next((item for item in channels if item["name"] == FIXTURE_NAME), None)
    if channel is None:
        channel = api_json(
            api_url,
            "/api/v3/channels",
            "POST",
            {
                "name": FIXTURE_NAME,
                "language": "English",
                "niche": "2D animation production",
                "audience": "Independent animation teams",
            },
        )
    channel = api_json(
        api_url,
        f"/api/v3/channels/{channel['channel_id']}/channel-dna",
        "POST",
        {"channel_dna": fixture_dna()},
    )

    projects = api_json(api_url, "/api/v3/projects")["items"]
    project = next(
        (
            item
            for item in projects
            if item["channel_id"] == channel["channel_id"] and item["name"] == PROJECT_NAME
        ),
        None,
    )
    if project is None:
        project = api_json(
            api_url,
            "/api/v3/projects",
            "POST",
            {
                "channel_id": channel["channel_id"],
                "name": PROJECT_NAME,
                "description": "Disposable evidence fixture for the C0 G0 baseline capture.",
            },
        )
    return channel, project


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def wait_for_shell(page: Page, expected_text: str) -> None:
    page.wait_for_load_state("domcontentloaded")
    page.get_by_text(expected_text, exact=True).first.wait_for(state="visible", timeout=20_000)
    page.wait_for_timeout(700)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--frontend-url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--browser-executable", type=Path, required=True)
    parser.add_argument("--baseline-sha", default=AUDITED_BASELINE)
    args = parser.parse_args()

    if args.baseline_sha != AUDITED_BASELINE:
        raise SystemExit(f"Refusing non-audited baseline {args.baseline_sha}; expected {AUDITED_BASELINE}")
    if not args.browser_executable.is_file():
        raise SystemExit(f"Browser executable not found: {args.browser_executable}")

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    channel, project = seed_disposable_data(args.api_url)
    captured_at = datetime.now(timezone.utc).isoformat()
    records: list[dict[str, Any]] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=str(args.browser_executable),
            headless=True,
            args=["--disable-gpu", "--disable-vulkan"],
        )
        browser_version = browser.version

        def capture(
            name: str,
            route: str,
            viewport: tuple[int, int],
            expected_text: str,
            action: str = "navigate",
        ) -> None:
            context = browser.new_context(
                viewport={"width": viewport[0], "height": viewport[1]},
                device_scale_factor=1,
                reduced_motion="reduce",
            )
            selection = json.dumps([channel["channel_id"], project["project_id"]])
            context.add_init_script(
                "const [channelId, projectId] = " + selection + ";"
                "localStorage.setItem('selectedChannelId', channelId);"
                "localStorage.setItem('selectedProjectId', projectId);"
            )
            page = context.new_page()
            page.goto(f"{args.frontend_url.rstrip('/')}{route}", wait_until="domcontentloaded")
            wait_for_shell(page, expected_text)
            if action == "open-channel-modal":
                page.get_by_role("button", name="Create Channel", exact=True).click()
                page.get_by_text("Channel DNA Setup", exact=True).wait_for(state="visible")
            elif action == "open-project-modal":
                page.get_by_test_id("new-project-button").click()
                page.get_by_text("Create Project", exact=True).first.wait_for(state="visible")
            file_path = output / f"{name}.png"
            page.screenshot(path=str(file_path), full_page=False)
            records.append(
                {
                    "file": file_path.relative_to(Path.cwd().resolve()).as_posix(),
                    "sha256": sha256(file_path),
                    "bytes": file_path.stat().st_size,
                    "route": route,
                    "viewport": {"width": viewport[0], "height": viewport[1]},
                    "expected_visible_text": expected_text,
                    "browser_action": action,
                }
            )
            context.close()

        capture("01-channels-dna-editor-1440x900", "/", (1440, 900), "Channel DNA")
        capture("02-create-channel-modal-1440x900", "/", (1440, 900), "Channels", "open-channel-modal")
        capture("03-projects-1440x900", "/projects", (1440, 900), "Projects")
        capture("04-create-project-modal-1440x900", "/projects", (1440, 900), "Projects", "open-project-modal")
        capture("05-studio-pipeline-1440x900", "/studio", (1440, 900), "Studio")
        capture("06-settings-1440x900", "/settings", (1440, 900), "Settings")
        capture("07-jobs-1440x900", "/jobs", (1440, 900), "Jobs")
        capture("08-artifacts-1440x900", "/artifacts", (1440, 900), "Artifacts")
        capture("09-studio-wide-1920x1080", "/studio", (1920, 1080), "Studio")
        capture("10-channels-narrow-768x900", "/", (768, 900), "Channel DNA")
        browser.close()

    manifest = {
        "gate": "G0",
        "status": "CAPTURED",
        "baseline_commit": args.baseline_sha,
        "source_assertion": "Frontend bytes were verified identical to the audited baseline before capture.",
        "captured_at_utc": captured_at,
        "browser": {"product": "Google Chrome via Playwright Chromium driver", "version": browser_version},
        "host_os": platform.platform(),
        "frontend_url": args.frontend_url,
        "api_url": args.api_url,
        "data_policy": "Synthetic records in a disposable migrated SQLite database only.",
        "fixture": {"channel_id": channel["channel_id"], "project_id": project["project_id"]},
        "screenshots": records,
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"PASS screenshots={len(records)} manifest={manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
