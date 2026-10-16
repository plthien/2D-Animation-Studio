#!/usr/bin/env python3
"""Verify committed G0 browser evidence and its cryptographic manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

BASELINE = "b35834808d99067e362a6e728ce7af8e04d2b6bd"
REQUIRED_ROUTES = {"/", "/projects", "/studio", "/settings", "/jobs", "/artifacts"}
REQUIRED_VIEWPORTS = {(1440, 900), (1920, 1080), (768, 900)}
REQUIRED_ACTIONS = {"navigate", "open-channel-modal", "open-project-modal"}


def validate(root: Path, manifest_path: Path) -> list[str]:
    errors: list[str] = []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [f"cannot read manifest: {exc}"]
    if manifest.get("gate") != "G0" or manifest.get("status") != "CAPTURED":
        errors.append("manifest must identify captured G0 evidence")
    if manifest.get("baseline_commit") != BASELINE:
        errors.append("manifest baseline commit is not the audited YTB baseline")
    if not manifest.get("browser", {}).get("version") or not manifest.get("host_os"):
        errors.append("browser version and host OS are required")
    if not manifest.get("fixture", {}).get("channel_id") or not manifest.get("fixture", {}).get("project_id"):
        errors.append("synthetic fixture identifiers are required")
    screenshots = manifest.get("screenshots")
    if not isinstance(screenshots, list) or len(screenshots) != 10:
        return errors + ["exactly 10 screenshot records are required"]
    routes: set[str] = set()
    viewports: set[tuple[int, int]] = set()
    actions: set[str] = set()
    seen_files: set[str] = set()
    for index, item in enumerate(screenshots):
        if not isinstance(item, dict):
            errors.append(f"screenshot {index} is not an object")
            continue
        relative = item.get("file")
        if not isinstance(relative, str) or relative in seen_files:
            errors.append(f"screenshot {index} has a missing or duplicate path")
            continue
        seen_files.add(relative)
        candidate = (root / relative).resolve()
        try:
            candidate.relative_to(root.resolve())
        except ValueError:
            errors.append(f"screenshot path escapes repository: {relative}")
            continue
        if not candidate.is_file():
            errors.append(f"missing screenshot: {relative}")
            continue
        payload = candidate.read_bytes()
        if not payload.startswith(b"\x89PNG\r\n\x1a\n"):
            errors.append(f"not a PNG: {relative}")
        digest = hashlib.sha256(payload).hexdigest()
        if item.get("sha256") != digest or item.get("bytes") != len(payload):
            errors.append(f"hash/size mismatch: {relative}")
        viewport = item.get("viewport", {})
        viewports.add((viewport.get("width"), viewport.get("height")))
        routes.add(item.get("route"))
        actions.add(item.get("browser_action"))
    if not REQUIRED_ROUTES.issubset(routes):
        errors.append(f"missing routes: {sorted(REQUIRED_ROUTES - routes)}")
    if not REQUIRED_VIEWPORTS.issubset(viewports):
        errors.append(f"missing viewports: {sorted(REQUIRED_VIEWPORTS - viewports)}")
    if not REQUIRED_ACTIONS.issubset(actions):
        errors.append(f"missing browser actions: {sorted(REQUIRED_ACTIONS - actions)}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--manifest", type=Path, default=Path("docs/qa/evidence/g0/manifest.json"))
    args = parser.parse_args()
    root = args.root.resolve()
    manifest_path = args.manifest if args.manifest.is_absolute() else root / args.manifest
    errors = validate(root, manifest_path)
    if errors:
        print("FAIL G0 evidence")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS screenshots=10 routes=6 viewports=3 actions=3 hashes=verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
