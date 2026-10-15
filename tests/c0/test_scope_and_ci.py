from pathlib import Path

from tools.check_c0_scope import EXACT, FORBIDDEN_PREFIXES, PREFIXES


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/c0-contract-audit.yml"
REFRESH = ROOT / ".github/workflows/refresh-release-manifest.yml"
LEGACY_AUDIT = ROOT / ".github/workflows/scene-assets-v2-candidate-audit.yml"


def allowed(path: str) -> bool:
    return not path.startswith(FORBIDDEN_PREFIXES) and (path in EXACT or path.startswith(PREFIXES))


def test_scope_rejects_production_and_unrelated_paths() -> None:
    assert not allowed("app/main.py")
    assert not allowed("src/App.tsx")
    assert not allowed("alembic/versions/032_animation.py")
    assert not allowed("requirements.txt")
    assert allowed("contracts/animation/animation_schema.sql")
    assert allowed("tests/c0/test_database_contract.py")


def test_dedicated_ci_has_exact_head_linux_windows_and_all_gates() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    for required in (
        "pull_request:", "github.event.pull_request.head.sha", "ubuntu-latest", "windows-latest",
        "python-version: '3.12'", "tools/check_c0_ledger.py", "tools/verify_c0_reachability.py",
        "tools/check_c0_db_contract.py", "tools/validate_c0_contracts.py", "tools/check_g0_evidence.py",
        "tools/check_c0_scope.py", "python -m pytest tests/c0 -q --confcutdir=tests/c0", "git diff --check",
    ):
        assert required in text


def test_release_refresh_exempts_only_c0_branch() -> None:
    text = REFRESH.read_text(encoding="utf-8")
    assert "branches-ignore:" in text
    assert "feat/c0-clean-cutover-contracts" in text
    assert "branches-ignore:\n      - '*'" not in text
    legacy = LEGACY_AUDIT.read_text(encoding="utf-8")
    assert "Record C0 manifest freeze" in legacy
    assert legacy.count("github.head_ref != 'feat/c0-clean-cutover-contracts'") == 3
