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


def test_windows_only_c0_and_transitional_ci_contract() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    for required in (
        "pull_request:", "github.event.pull_request.head.sha", "windows-latest", "shell: pwsh",
        "python-version: '3.12'", "tools/check_c0_ledger.py", "tools/verify_c0_reachability.py",
        "tools/check_c0_db_contract.py", "tools/validate_c0_contracts.py", "tools/check_g0_evidence.py",
        "tools/check_c0_scope.py", "python -m pytest tests/c0 -q --confcutdir=tests/c0", "git diff --check",
    ):
        assert required in text
    assert text.count("runs-on: windows-latest") == 1
    assert "c0-linux:" not in text
    for path in (WORKFLOW, REFRESH, LEGACY_AUDIT):
        active_workflow = path.read_text(encoding="utf-8")
        assert "runs-on: windows-latest" in active_workflow
        assert "runs-on: ubuntu-latest" not in active_workflow
        assert "runs-on: macos-latest" not in active_workflow


def test_release_refresh_exempts_only_c0_branch() -> None:
    text = REFRESH.read_text(encoding="utf-8")
    assert "branches-ignore:" in text
    assert "feat/c0-clean-cutover-contracts" in text
    assert "branches-ignore:\n      - '*'" not in text
    legacy = LEGACY_AUDIT.read_text(encoding="utf-8")
    assert "Record C0 manifest freeze" in legacy
    assert "github.head_ref != 'feat/c0-clean-cutover-contracts'" in legacy
    assert "github.ref_name != 'feat/c0-clean-cutover-contracts'" in text
    assert "fetch-depth: 0" in legacy
