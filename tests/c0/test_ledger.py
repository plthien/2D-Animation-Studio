from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from c0_ledger_lib import LEDGER_COLUMNS, PROTECTED_UI, analyze_reachability, baseline_paths, parse_ledger  # noqa: E402


@pytest.fixture(scope="module")
def ledger_text() -> str:
    return (ROOT / "docs/architecture/CLEAN_CUT_FILE_LEDGER.md").read_text(encoding="utf-8")


def test_ledger_accounts_for_exact_baseline_once(ledger_text: str) -> None:
    rows = parse_ledger(ledger_text)
    paths = [row["path"] for row in rows]
    assert len(paths) == 813
    assert len(paths) == len(set(paths))
    assert set(paths) == set(baseline_paths())


def test_reachable_files_and_protected_ui_are_not_discarded(ledger_text: str) -> None:
    rows = {row["path"]: row for row in parse_ledger(ledger_text)}
    reach = analyze_reachability(baseline_paths())
    for path, evidence in reach.items():
        if evidence.active == "yes":
            assert rows[path]["active_runtime_dependency"] == "yes", path
            assert rows[path]["entrypoint_root"] != "-", path
    for path in PROTECTED_UI:
        assert rows[path]["classification"] in {"KEEP", "ADAPT"}


def test_every_extract_has_symbol_destination_and_regression(ledger_text: str) -> None:
    for row in parse_ledger(ledger_text):
        if row["classification"] == "EXTRACT":
            assert row["target_owner_path"] not in {"-", "N/A", "removed"}
            assert row["extraction_responsibility"] not in {"-", "N/A"}
            assert row["replacement_or_retained_test"].startswith("tests/")


@pytest.mark.parametrize(
    "mutator",
    [
        lambda lines: [line for line in lines if not line.startswith("app/main.py\t")],
        lambda lines: lines + [next(line for line in lines if line.startswith("app/main.py\t"))],
        lambda lines: [line.replace("app/main.py\tADAPT\t", "app/main.py\tUNKNOWN\t") if line.startswith("app/main.py\t") else line for line in lines],
        lambda lines: [line.replace("\tyes\tapp/main.py\t", "\tno\tapp/main.py\t") if line.startswith("app/main.py\t") else line for line in lines],
        lambda lines: ["\t".join((lambda fields: fields[:5] + ["N/A"] + fields[6:])(line.split("\t"))) if line.startswith("app/repositories/core.py\t") else line for line in lines],
    ],
)
def test_ledger_mutations_are_observable(ledger_text: str, mutator) -> None:
    lines = ledger_text.splitlines()
    start, end = lines.index("```tsv"), lines.index("```", lines.index("```tsv") + 1)
    prefix, table, suffix = lines[: start + 2], lines[start + 2:end], lines[end:]
    mutated = "\n".join(prefix + mutator(table) + suffix)
    try:
        rows = parse_ledger(mutated)
    except ValueError:
        return
    paths = [row["path"] for row in rows]
    valid = (
        len(paths) == 813
        and len(paths) == len(set(paths))
        and set(paths) == set(baseline_paths())
        and all(row["classification"] in {"KEEP", "ADAPT", "EXTRACT", "DELETE"} for row in rows)
        and all(not (row["classification"] == "EXTRACT" and row["extraction_responsibility"] in {"N/A", "-"}) for row in rows)
        and next(row for row in rows if row["path"] == "app/main.py")["active_runtime_dependency"] == "yes"
    )
    assert not valid
