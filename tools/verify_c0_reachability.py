"""Print the deterministic baseline reachability report; does not modify files."""
from __future__ import annotations
import argparse
import json
from collections import Counter
from c0_ledger_lib import analyze_reachability, baseline_paths

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="emit all per-path dependency chains")
    args = parser.parse_args()
    paths = baseline_paths()
    report = analyze_reachability(paths)
    if args.json:
        print(json.dumps({p: report[p].__dict__ for p in paths}, indent=2, sort_keys=True))
    else:
        counts = Counter(item.active for item in report.values())
        roots = sorted({item.root for item in report.values() if item.root != "-"})
        print(
            f"PASS tracked={len(paths)} reachable={counts['yes']} unreachable={counts['no']} "
            f"unknown={counts['unknown']} roots={len(roots)}"
        )
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
