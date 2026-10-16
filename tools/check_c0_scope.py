#!/usr/bin/env python3
"""Reject C0 changes outside the contract-freeze allowlist."""

from __future__ import annotations

import argparse
import ast
import subprocess
from pathlib import Path
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
    # C0-EXIT-01: only the inherited Bash-dependent manifest assertion may change.
    "tests/v4/test_kokoro_setup_static.py",
}
PREFIXES = ("contracts/animation/", "docs/architecture/", "docs/plans/", "docs/qa/", "tests/c0/")
FORBIDDEN_PREFIXES = ("app/", "src/", "alembic/versions/")
LEGACY_TEST_EXCEPTION = "tests/v4/test_kokoro_setup_static.py"
LEGACY_TEST_FUNCTION = "test_release_manifest_refresh_targets_active_branch"


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



def legacy_test_repair_is_narrow(base: str) -> bool:
    """Allow edits to only the approved manifest-regression function, not other tests."""
    old = subprocess.run(
        ["git", "show", f"{base}:{LEGACY_TEST_EXCEPTION}"],
        check=True, capture_output=True, text=True, encoding="utf-8",
    ).stdout
    current = Path(LEGACY_TEST_EXCEPTION).read_text(encoding="utf-8")

    def masked_tree(source: str) -> str:
        tree = ast.parse(source)
        matches = [
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == LEGACY_TEST_FUNCTION
        ]
        if len(matches) != 1:
            raise ValueError("approved legacy test function missing or duplicated")
        matches[0].body = [ast.Pass()]
        return ast.dump(tree, include_attributes=False)

    try:
        return masked_tree(old) == masked_tree(current)
    except (OSError, SyntaxError, ValueError):
        return False

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
        elif path == LEGACY_TEST_EXCEPTION and (status != "M" or not legacy_test_repair_is_narrow(args.base)):
            errors.append(f"C0-EXIT-01 legacy test edits exceed authorized function: {status} {path}")
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
