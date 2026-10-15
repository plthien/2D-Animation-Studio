"""C0-only baseline ledger completeness gate; no production imports."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "docs/architecture/CLEAN_CUT_FILE_LEDGER.md"
ALLOWED = {"KEEP", "ADAPT", "EXTRACT", "DELETE"}
BASELINE_SHA = "b35834808d99067e362a6e728ce7af8e04d2b6bd"


def main() -> int:
    # C0 deliverables are deliberately unclassified: the ledger freezes the
    # source tree it audits, not files created while documenting that tree.
    tracked = set(subprocess.check_output(
        ["git", "ls-tree", "-r", "--name-only", BASELINE_SHA], cwd=ROOT, text=True
    ).splitlines())
    lines = LEDGER.read_text(encoding="utf-8").splitlines()
    try:
        start = lines.index("```tsv") + 2
        end = lines.index("```", start)
    except ValueError:
        print("FAIL: inventory TSV markers/header missing")
        return 1
    rows = [line.split("\t") for line in lines[start:end] if line]
    bad = [row for row in rows if len(row) != 9 or row[1] not in ALLOWED or not all(row)]
    paths = [row[0] for row in rows]
    duplicate = sorted({p for p in paths if paths.count(p) > 1})
    listed = set(paths)
    missing, unexpected = sorted(tracked - listed), sorted(listed - tracked)
    if bad or duplicate or missing or unexpected:
        print(f"FAIL rows={len(rows)} tracked={len(tracked)} bad={len(bad)} duplicate={duplicate[:5]} missing={missing[:5]} unexpected={unexpected[:5]}")
        return 1
    counts = {name: sum(row[1] == name for row in rows) for name in sorted(ALLOWED)}
    print(f"PASS tracked={len(tracked)} rows={len(rows)} " + " ".join(f"{k}={v}" for k, v in counts.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
