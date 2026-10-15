"""Strict C0 schema, fixture, and cross-artifact semantic validator."""
from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "contracts/animation/schemas"
VALID_PATH = ROOT / "contracts/animation/examples/valid/catalog.json"
INVALID_PATH = ROOT / "contracts/animation/examples/invalid/cases.json"
REQUIRED = {"channel_dna.v2","topic_ideas.v1","script.v1","script_analysis.v1","shot_plan.v1","asset_requirements.v1","asset_resolution.v1","asset_version.v1","parts_manifest.v1","rig_profile.v1","rig_manifest.v1","animation_plan.v1","compiled_film.v1","render_manifest.v1","voice_manifest.v1","final_timeline.v1","final_video.v1","qc_report.v1"}
ACTIONS = {"idle","walk_to","look_at","reach_for","grab","carry_to","place_at","point_at","react"}
TARGET_REQUIRED = {"walk_to","look_at","reach_for","grab","carry_to","place_at","point_at"}
PARTS = {"head","torso","pelvis","upper_arm_l","lower_arm_l","hand_l","upper_arm_r","lower_arm_r","hand_r","upper_leg_l","lower_leg_l","foot_l","upper_leg_r","lower_leg_r"}
REQUIRED_BONES = {"root","hip","chest","neck","head","left_upper_arm","left_lower_arm","left_hand","right_upper_arm","right_lower_arm","right_hand","left_upper_leg","left_lower_leg","left_foot","right_upper_leg","right_lower_leg"}


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_pairs, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"non-finite JSON number: {value}")))


def load_schemas() -> dict[str, dict[str, Any]]:
    schemas = {path.name.removesuffix(".schema.json"): load_json(path) for path in SCHEMAS.glob("*.schema.json")}
    if set(schemas) != REQUIRED:
        raise ValueError(f"contract set mismatch missing={sorted(REQUIRED-set(schemas))} extra={sorted(set(schemas)-REQUIRED)}")
    ids = [value.get("$id") for value in schemas.values()]
    if len(ids) != len(set(ids)) or any(not value for value in ids):
        raise ValueError("schema $id values must be present and unique")
    for value in schemas.values():
        Draft202012Validator.check_schema(value)
    return schemas


def schema_errors(schema: dict[str, Any], document: Any) -> list[str]:
    errors = Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(document)
    return [f"{'/'.join(map(str,error.absolute_path))}: {error.message} [{error.validator}]" for error in sorted(errors,key=lambda error:list(error.absolute_path))]


def semantic_validate_bundle(bundle: dict[str, dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    def err(message: str) -> None: errors.append(message)
    channels = {doc["channel_id"] for doc in bundle.values()}
    projects = {doc["project_id"] for doc in bundle.values() if "project_id" in doc}
    if len(channels) != 1: err("channel ownership mismatch")
    if len(projects) != 1: err("project ownership mismatch")

    script, plan = bundle["script.v1"], bundle["shot_plan.v1"]
    if plan["script_artifact_id"] != script["artifact_id"]: err("ShotPlan script lineage mismatch")
    actor_ids, prop_ids, location_ids = set(plan["actor_ids"]), set(plan["prop_ids"]), set(plan["location_ids"])
    shot_ids: set[str] = set()
    shots: dict[str, dict[str, Any]] = {}
    for shot in plan["shots"]:
        if shot["shot_id"] in shot_ids: err("duplicate shot_id")
        shot_ids.add(shot["shot_id"]); shots[shot["shot_id"]] = shot
        if not 24 <= shot["duration_frames"] <= 720: err("shot duration outside 24..720")
        if not set(shot["actor_ids"]) <= actor_ids or not set(shot["prop_ids"]) <= prop_ids or shot["location_id"] not in location_ids: err("shot entity reference missing")
        utterance = shot["utterance"]
        if utterance:
            start, end = utterance["script_start"], utterance["script_end"]
            if not (0 <= start < end <= len(script["full_text"])) or script["full_text"][start:end] != utterance["text"]: err("utterance range/text mismatch")

    requirements = bundle["asset_requirements.v1"]
    if requirements["shot_plan_artifact_id"] != plan["artifact_id"]: err("asset requirement lineage mismatch")
    req_by_id: dict[str, dict[str, Any]] = {}
    req_keys: set[tuple[str,str,str]] = set()
    for req in requirements["requirements"]:
        key=(req["kind"],req["semantic_key"],req["view"])
        if req["requirement_id"] in req_by_id or key in req_keys: err("duplicate asset requirement")
        req_by_id[req["requirement_id"]]=req;req_keys.add(key)
        if not set(req["shot_ids"]) <= shot_ids: err("asset requirement shot missing")
    for pin in bundle["asset_resolution.v1"]["pins"]:
        req=req_by_id.get(pin["requirement_id"])
        if req is None: err("nonexistent asset-resolution pin");continue
        if (pin["kind"],pin["semantic_key"],pin["view"]) != (req["kind"],req["semantic_key"],req["view"]): err("asset pin compatibility mismatch")
        if pin["asset_channel_id"] != plan["channel_id"] or pin["approval_status"] != "approved": err("asset pin ownership/approval mismatch")

    parts=bundle["parts_manifest.v1"]["parts"]
    roles=[part["role"] for part in parts]
    if len(roles)!=14 or set(roles)!=PARTS: err("parts must contain 14 unique semantic roles")
    for part in parts:
        pivot=part["pivot"]
        if not all(isinstance(pivot.get(key),(int,float)) and math.isfinite(pivot[key]) and 0 <= pivot[key] <= 1 for key in ("x","y")): err("invalid normalized pivot")
        if not part["reviewed"]: err("unreviewed part evidence")
    profile=bundle["rig_profile.v1"]
    bone_roles=[bone["role"] for bone in profile["bones"]]
    if len(bone_roles)!=len(set(bone_roles)) or not REQUIRED_BONES <= set(bone_roles): err("rig requires unique semantic bones")
    capabilities=set(profile["capabilities"])

    actions=bundle["animation_plan.v1"]["actions"]
    actor_spans: dict[tuple[str,str],list[tuple[int,int,str]]] = {}
    held: dict[tuple[str,str],str] = {}
    for action in actions:
        shot=shots.get(action["shot_id"])
        if shot is None: err("action references missing shot");continue
        if action["actor_id"] not in shot["actor_ids"]: err("action actor not in shot")
        if not 0 <= action["start_frame"] < action["end_frame"] <= shot["duration_frames"]: err("action outside shot bounds")
        if action["action"] not in capabilities: err("rig capability mismatch")
        if action["action"] in TARGET_REQUIRED and not (action["target_id"] or action["prop_id"]): err("action target required")
        if action["prop_id"] and action["prop_id"] not in shot["prop_ids"]: err("action prop not in shot")
        key=(action["shot_id"],action["actor_id"]); actor_spans.setdefault(key,[]).append((action["start_frame"],action["end_frame"],action["action_id"]))
        hand=(action["actor_id"],action["hand"])
        if action["action"]=="grab":
            if action["hand"]=="none" or hand in held: err("one prop per hand violated")
            elif action["prop_id"]: held[hand]=action["prop_id"]
        if action["action"]=="place_at":
            if held.get(hand)!=action["prop_id"]: err("release without matching grip")
            else: del held[hand]
    for spans in actor_spans.values():
        spans.sort()
        if any(spans[i][0] < spans[i-1][1] for i in range(1,len(spans))): err("overlapping actor actions")

    compiled=bundle["compiled_film.v1"]
    if compiled["animation_plan_artifact_id"]!=bundle["animation_plan.v1"]["artifact_id"]: err("compiled animation lineage mismatch")
    offset=0
    for cshot in compiled["shots"]:
        if cshot["global_start_frame"]!=offset: err("compiled shot ordering/gap mismatch")
        offset+=cshot["frame_count"]
    render=bundle["render_manifest.v1"]
    frames=render["frames"]
    if [frame["frame"] for frame in frames] != list(range(offset)): err("render frames must be exact ordered complete set")
    compiled_by_shot={shot["shot_id"]:shot for shot in compiled["shots"]}
    for frame in frames:
        if frame["shot_id"] not in compiled_by_shot: err("render frame shot missing")

    voice=bundle["voice_manifest.v1"]
    if voice["script_artifact_id"]!=script["artifact_id"] or voice["render_manifest_artifact_id"]!=render["artifact_id"]: err("voice-last lineage mismatch")
    for voiced in voice["voiced_shots"]:
        if voiced["shot_id"] not in shot_ids: err("voice shot missing")
        if voiced["sample_count"] != (voiced["end_frame"]-voiced["start_frame"])*2000: err("voice sample/frame count mismatch")
        if script["full_text"][voiced["script_start"]:voiced["script_end"]] != voiced["text"]: err("voice text not exact script range")
    timeline=bundle["final_timeline.v1"]
    for shot in timeline["shots"]:
        if shot["final_duration_frames"] != shot["base_duration_frames"]+shot["terminal_hold_frames"]: err("final duration/hold mismatch")
        if shot["voiced_start_frame"] is None:
            if shot["audio_sample_count"]!=0 or shot["voiced_end_frame"] is not None: err("silent shot has fabricated narration")
        elif shot["audio_sample_count"] != (shot["voiced_end_frame"]-shot["voiced_start_frame"])*2000: err("timeline absolute sample/frame mismatch")
    return errors


def validate_all() -> tuple[int,int,int]:
    schemas=load_schemas();valid=load_json(VALID_PATH);invalid=load_json(INVALID_PATH)
    if set(valid)!=REQUIRED or set(invalid)!=REQUIRED: raise ValueError("fixture completeness mismatch")
    canonical: dict[str,dict[str,Any]]={}
    positive_count=0
    for name in sorted(REQUIRED):
        if len(valid[name])<2: raise ValueError(f"{name} requires at least two valid fixtures")
        for document in valid[name]:
            found=schema_errors(schemas[name],document)
            if found: raise ValueError(f"valid {name} failed: {found[0]}")
            positive_count+=1
        canonical[name]=valid[name][0]
    semantic=semantic_validate_bundle(canonical)
    if semantic: raise ValueError(f"valid cross-artifact bundle failed: {semantic}")
    negative_count=0
    for name in sorted(REQUIRED):
        if len(invalid[name])<4: raise ValueError(f"{name} requires at least four invalid fixtures")
        for case in invalid[name]:
            if case["mode"]=="schema":
                found=schema_errors(schemas[name],case["document"])
                if not found: raise ValueError(f"invalid {name}/{case['name']} was accepted")
                haystack=" ".join(found).lower()
            else:
                mutated={key:value[0].copy() for key,value in valid.items()}
                mutated[name]=case["document"]
                haystack=" ".join(semantic_validate_bundle(mutated)).lower()
            expected=case["expected"].lower().replace(".","/")
            if expected not in haystack: raise ValueError(f"invalid {name}/{case['name']} failed for wrong reason: {haystack[:300]}")
            negative_count+=1
    return len(schemas),positive_count,negative_count


def main() -> int:
    schema_count,positive_count,negative_count=validate_all()
    print(f"PASS schemas={schema_count} positive={positive_count} negative={negative_count} semantic_bundle=1")
    return 0
if __name__=="__main__": raise SystemExit(main())
