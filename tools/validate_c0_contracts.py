"""C0 schema + semantic gate. Fixtures intentionally never call product code."""
from __future__ import annotations
import json
from pathlib import Path
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "contracts" / "animation" / "schemas"
VALID = json.loads((ROOT / "contracts/animation/examples/valid/catalog.json").read_text())
INVALID = json.loads((ROOT / "contracts/animation/examples/invalid/catalog.json").read_text())

def schema(name: str): return json.loads((SCHEMAS / f"{name}.schema.json").read_text())
def errors(name: str, value: object): return list(Draft202012Validator(schema(name)).iter_errors(value))

def main() -> int:
    names = [p.name.removesuffix(".schema.json") for p in SCHEMAS.glob("*.schema.json")]
    required = {"channel_dna.v2","topic_ideas.v1","script.v1","script_analysis.v1","shot_plan.v1","asset_requirements.v1","asset_resolution.v1","asset_version.v1","parts_manifest.v1","rig_profile.v1","rig_manifest.v1","animation_plan.v1","compiled_film.v1","render_manifest.v1","voice_manifest.v1","final_timeline.v1","final_video.v1","qc_report.v1"}
    if set(names) != required: raise SystemExit(f"FAIL contract set missing={sorted(required-set(names))} extra={sorted(set(names)-required)}")
    for name, fixture in VALID.items():
        if errors(name, fixture): raise SystemExit(f"FAIL valid {name}: {errors(name, fixture)[0].message}")
    for name, fixture in INVALID.items():
        if not errors(name, fixture): raise SystemExit(f"FAIL invalid {name} accepted")
    shot, plan, timeline = VALID["shot_plan.v1"], VALID["animation_plan.v1"], VALID["final_timeline.v1"]
    if plan["shot_plan_artifact_id"] != shot["artifact_id"]: raise SystemExit("FAIL plan source")
    shot_ids = {x["shot_id"] for x in shot["shots"]}
    if any(x["shot_id"] not in shot_ids or x["end_frame"] <= x["start_frame"] for x in plan["actions"]): raise SystemExit("FAIL action interval/reference")
    if any(x["final_end_frame"] - x["base_end_frame"] > 48 or x["audio_sample_count"] % 2000 for x in timeline["shots"]): raise SystemExit("FAIL final reconciliation")
    print(f"PASS schemas={len(names)} valid={len(VALID)} invalid={len(INVALID)} semantic=3")
    return 0
if __name__ == "__main__": raise SystemExit(main())
