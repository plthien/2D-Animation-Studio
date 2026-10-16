"""C0-only baseline ledger completeness gate; no production imports."""
from __future__ import annotations

import sys
from pathlib import Path

from c0_ledger_lib import ALLOWED, BASELINE_SHA, PROTECTED_UI, analyze_reachability, baseline_paths, parse_ledger

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "docs/architecture/CLEAN_CUT_FILE_LEDGER.md"


def main() -> int:
    # C0 deliverables are deliberately unclassified: the ledger freezes the
    # source tree it audits, not files created while documenting that tree.
    try:
        rows = parse_ledger(LEDGER.read_text(encoding="utf-8"))
    except ValueError as exc:
        print(f"FAIL: {exc}")
        return 1
    tracked = set(baseline_paths())
    paths = [row["path"] for row in rows]
    seen: set[str] = set()
    duplicate: set[str] = set()
    for path in paths:
        if path in seen:
            duplicate.add(path)
        seen.add(path)
    listed = set(paths)
    missing, unexpected = sorted(tracked - listed), sorted(listed - tracked)
    bad = [row["path"] for row in rows if row["classification"] not in ALLOWED or not all(row.values())]
    bad_extract = [row["path"] for row in rows if row["classification"] == "EXTRACT" and row["extraction_responsibility"] in {"-", "N/A"}]
    computed = analyze_reachability(list(tracked))
    bad_active = [row["path"] for row in rows if computed[row["path"]].active == "yes" and row["active_runtime_dependency"] != "yes"]
    bad_protected = [row["path"] for row in rows if row["path"] in PROTECTED_UI and row["classification"] not in {"KEEP", "ADAPT"}]
    if bad or duplicate or missing or unexpected or bad_extract or bad_active or bad_protected:
        print(f"FAIL rows={len(rows)} tracked={len(tracked)} bad={bad[:5]} duplicate={sorted(duplicate)[:5]} missing={missing[:5]} unexpected={unexpected[:5]} bad_extract={bad_extract[:5]} bad_active={bad_active[:5]} bad_protected={bad_protected[:5]}")
        return 1
    counts = {name: sum(row["classification"] == name for row in rows) for name in sorted(ALLOWED)}
    print(f"PASS tracked={len(tracked)} rows={len(rows)} " + " ".join(f"{k}={v}" for k, v in counts.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
