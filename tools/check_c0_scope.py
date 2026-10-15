#!/usr/bin/env python3
"""Reject C0 changes outside the contract-freeze allowlist."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import PurePosixPath

DEFAULT_BASE = "b35834808d99067e362a6e728ce7af8e04d2b6bd"
EXACT = {
    "AGENTS.md",
    ".github/workflows/c0-contract-audit.yml",
    ".github/workflows/refresh-release-manifest.yml",
    ".github/workflows/scene-assets-v2-candidate-audit.yml",
    "MANIFEST.json",
    "tools/check_c0_ledger.py",
    "tools/validate_c0_contracts.py",
    "tools/c0_ledger_lib.py",
    "tools/check_c0_db_contract.py",
    "tools/render_c0_ledger.py",
    "tools/verify_c0_reachability.py",
    "tools/check_g0_evidence.py",
    "tools/capture_g0_baseline.py",
    "tools/check_c0_scope.py",
    "tools/requirements-c0.txt",
}
PREFIXES = ("contracts/animation/", "docs/architecture/", "docs/plans/", "docs/qa/", "tests/c0/")
FORBIDDEN_PREFIXES = ("app/", "src/", "alembic/versions/")


def changed(base: str, head: str) -> list[tuple[str, str]]:
    result = subprocess.run(
        ["git", "diff", "--name-status", f"{base}...{head}"],
        check=True,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
    )
    rows: list[tuple[str, str]] = []
    for line in result.stdout.splitlines():
        fields = line.split("\t")
        status = fields[0]
        path = fields[-1].replace("\\", "/")
        rows.append((status, PurePosixPath(path).as_posix()))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default=DEFAULT_BASE)
    parser.add_argument("--head", default="HEAD")
    args = parser.parse_args()
    rows = changed(args.base, args.head)
    errors: list[str] = []
    for status, path in rows:
        if path.startswith(FORBIDDEN_PREFIXES):
            errors.append(f"production path changed: {status} {path}")
        elif path not in EXACT and not path.startswith(PREFIXES):
            errors.append(f"path outside C0 allowlist: {status} {path}")
    if errors:
        print("FAIL C0 scope")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"PASS changed_paths={len(rows)} production_paths=0 base={args.base} head={args.head}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
