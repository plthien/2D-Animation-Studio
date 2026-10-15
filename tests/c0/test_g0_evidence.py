import json
import shutil
from pathlib import Path

from tools.check_g0_evidence import validate


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "docs/qa/evidence/g0/manifest.json"


def test_committed_g0_evidence_is_complete_and_hashed() -> None:
    assert validate(ROOT, MANIFEST) == []


def test_missing_screenshot_fails_gate(tmp_path: Path) -> None:
    evidence = tmp_path / "docs/qa/evidence/g0"
    evidence.mkdir(parents=True)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for record in manifest["screenshots"]:
        source = ROOT / record["file"]
        target = tmp_path / record["file"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    missing = tmp_path / manifest["screenshots"][0]["file"]
    missing.unlink()
    mutated = evidence / "manifest.json"
    mutated.write_text(json.dumps(manifest), encoding="utf-8")
    assert any("missing screenshot" in error for error in validate(tmp_path, mutated))
