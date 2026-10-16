"""Strict C0 schema, fixture, and cross-artifact semantic validator."""
from __future__ import annotations

import json
import math
import copy
import hashlib
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
    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_pairs,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"non-finite JSON number: {value}")),
        parse_float=_finite_float,
    )


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"non-finite JSON number: {value}")
    return number


def _finite_errors(value: Any, path: str = "") -> list[str]:
    if isinstance(value, float) and not math.isfinite(value):
        return [f"non-finite JSON number at {path or '/'}"]
    if isinstance(value, dict):
        return [error for key, item in value.items() for error in _finite_errors(item, f"{path}/{key}")]
    if isinstance(value, list):
        return [error for i, item in enumerate(value) for error in _finite_errors(item, f"{path}/{i}")]
    return []


def canonical_json_bytes(value: Any) -> bytes:
    errors = _finite_errors(value)
    if errors:
        raise ValueError(errors[0])
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def canonical_json_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def apply_mutations(canonical: dict[str, Any], mutations: list[dict[str, Any]]) -> dict[str, Any]:
    """Small RFC6901-pointer subset: add, replace and remove only; never mutate the base."""
    result = copy.deepcopy(canonical)
    for mutation in mutations:
        op, path = mutation["op"], mutation["path"]
        tokens = path.split("/")[1:]
        if not path.startswith("/") or not tokens or any("~" in token for token in tokens):
            raise ValueError(f"unsupported mutation pointer: {path}")
        target: Any = result
        for token in tokens[:-1]:
            target = target[int(token)] if isinstance(target, list) else target[token]
        key: Any = int(tokens[-1]) if isinstance(target, list) else tokens[-1]
        if op == "remove":
            if isinstance(target, list):
                target.pop(key)
            else:
                del target[key]
        elif op == "replace":
            if isinstance(target, list):
                target[key] = mutation["value"]
            else:
                if key not in target:
                    raise ValueError(f"replace target missing: {path}")
                target[key] = mutation["value"]
        elif op == "add":
            if isinstance(target, list):
                target.insert(key, mutation["value"])
            else:
                if key in target:
                    raise ValueError(f"add target already present: {path}")
                target[key] = mutation["value"]
        else:
            raise ValueError(f"unknown fixture mutation operation: {op}")
    return result


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
    finite_errors = _finite_errors(document)
    if finite_errors:
        return finite_errors
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
        # C1 authority: every visible actor/prop is placed by the frozen shot,
        # never by renderer defaults or mutable last-frame memory.
        initial = shot["initial_world_state"]
        actor_placements = initial["actors"]
        prop_placements = initial["props"]
        if {p["actor_id"] for p in actor_placements} != set(shot["actor_ids"]) or len(actor_placements) != len(shot["actor_ids"]):
            err("initial world actor placement mismatch")
        if {p["prop_id"] for p in prop_placements} != set(shot["prop_ids"]) or len(prop_placements) != len(shot["prop_ids"]):
            err("initial world prop placement mismatch")
        anchors = shot["spatial_anchors"]
        anchor_ids = [a["anchor_id"] for a in anchors]
        if len(anchor_ids) != len(set(anchor_ids)):
            err("duplicate shot spatial anchor")
        if set(anchor_ids) & (set(shot["actor_ids"]) | set(shot["prop_ids"])):
            err("ambiguous shot spatial anchor identity")
        for entity in actor_placements + prop_placements + anchors:
            if any(isinstance(entity[coord], bool) or not isinstance(entity[coord], (int, float)) or not math.isfinite(entity[coord]) for coord in ("x", "y")):
                err("non-finite initial spatial coordinates")
        for prop in prop_placements:
            holder = prop["held_by"]
            if holder is not None:
                parts = holder.rsplit(":", 1)
                if len(parts) != 2 or parts[0] not in shot["actor_ids"] or parts[1] not in {"left", "right"}:
                    err("invalid initial prop owner")
        holders = [prop["held_by"] for prop in prop_placements if prop["held_by"] is not None]
        if len(set(holders)) != len(holders):
            err("one prop per initial hand violated")
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
    channel_spans: dict[tuple[str, str, str], list[tuple[int, int, str]]] = {}
    grip_events: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    seen_action_ids: set[str] = set()
    for action in actions:
        shot=shots.get(action["shot_id"])
        if shot is None: err("action references missing shot");continue
        if action["actor_id"] not in shot["actor_ids"]: err("action actor not in shot")
        if not 0 <= action["start_frame"] < action["end_frame"] <= shot["duration_frames"]: err("action outside shot bounds")
        if action["action"] not in capabilities: err("rig capability mismatch")
        if action["action"] in TARGET_REQUIRED:
            target_id = action["target_id"]
            if not target_id:
                err("action target required")
            else:
                matches: list[tuple[str, dict[str, Any]]] = []
                state = shot["initial_world_state"]
                matches += [("actor", obj) for obj in state["actors"] if obj["actor_id"] == target_id]
                matches += [("prop", obj) for obj in state["props"] if obj["prop_id"] == target_id]
                matches += [("anchor", obj) for obj in shot["spatial_anchors"] if obj["anchor_id"] == target_id]
                if not matches:
                    err("action target unknown or outside frozen shot scope")
                elif len(matches) != 1:
                    err("action target ambiguous")
                else:
                    target_type, target = matches[0]
                    permitted = {
                        "walk_to": {"actor", "prop", "anchor"},
                        "look_at": {"actor", "prop", "anchor"},
                        "reach_for": {"prop"},
                        "grab": {"prop"},
                        "carry_to": {"anchor"},
                        "place_at": {"anchor"},
                        "point_at": {"actor", "prop", "anchor"},
                    }[action["action"]]
                    if target_type not in permitted:
                        err("action target incompatible type")
                    if not all(isinstance(target.get(axis), (int, float)) and
                               not isinstance(target.get(axis), bool) and
                               math.isfinite(target[axis]) for axis in ("x", "y")):
                        err("action target missing finite spatial coordinates")
                    if action["action"] == "grab" and target_id != action["prop_id"]:
                        err("grab target must match owned prop")
                    if action["action"] == "reach_for" and action["prop_id"] and target_id != action["prop_id"]:
                        err("reach target prop mismatch")
        if action["prop_id"] and action["prop_id"] not in shot["prop_ids"]: err("action prop not in shot")
        if action["action_id"] in seen_action_ids:
            err("duplicate action_id")
        seen_action_ids.add(action["action_id"])
        kind, hand = action["action"], action["hand"]
        if kind in {"grab", "place_at", "reach_for", "point_at"} and hand == "none":
            err("hand-specific action requires left or right hand")
        if kind in {"idle", "walk_to", "look_at", "react"} and hand != "none":
            err("non-hand action must use hand=none")
        if kind in {"grab", "place_at", "carry_to"} and not action["prop_id"]:
            err("prop action requires prop_id")
        if kind == "carry_to":
            # Carrying is locomotion with a frozen grip. Multi-hand transfer is not part of C0.
            if hand == "none":
                err("carry_to requires held hand")
        # These resources are exclusively owned; distinct channels can overlap.
        channels = {
            "idle": ("locomotion",),
            "walk_to": ("locomotion",),
            "look_at": ("gaze",),
            "react": ("expression",),
            "reach_for": (f"{hand}_arm",),
            "point_at": (f"{hand}_arm",),
            "grab": (f"{hand}_arm",),
            "place_at": (f"{hand}_arm",),
            "carry_to": ("locomotion",),
        }[kind]
        for channel in channels:
            key = (action["shot_id"], action["actor_id"], channel)
            channel_spans.setdefault(key, []).append((action["start_frame"], action["end_frame"], action["action_id"]))
        if kind in {"grab", "place_at", "carry_to"} and hand != "none":
            grip_events.setdefault((action["shot_id"], action["actor_id"], hand), []).append(action)
    for key, spans in channel_spans.items():
        spans.sort()
        if any(spans[i][0] < spans[i - 1][1] for i in range(1, len(spans))):
            err(f"conflicting motion channel: {key[2]}")
    for key, events in grip_events.items():
        events.sort(key=lambda item: (item["start_frame"], item["end_frame"], item["action_id"]))
        held_prop: str | None = None
        for event in events:
            if event["action"] == "grab":
                if held_prop is not None:
                    err("one prop per hand violated")
                else:
                    held_prop = event["prop_id"]
            elif event["action"] == "carry_to":
                if held_prop != event["prop_id"]:
                    err("carry without matching grip")
            elif event["action"] == "place_at":
                if held_prop != event["prop_id"]:
                    err("release without matching grip")
                else:
                    held_prop = None

    compiled=bundle["compiled_film.v1"]
    if compiled["animation_plan_artifact_id"]!=bundle["animation_plan.v1"]["artifact_id"]: err("compiled animation lineage mismatch")
    if compiled["shot_plan_artifact_id"] != plan["artifact_id"]:
        err("compiled shot-plan lineage mismatch")
    approved_order = [shot["shot_id"] for shot in plan["shots"]]
    compiled_order = [shot["shot_id"] for shot in compiled["shots"]]
    if compiled_order != approved_order or len(compiled_order) != len(set(compiled_order)):
        err("compiled shot identity/order mismatch")
    compiled_by_shot: dict[str, dict[str, Any]] = {}
    offset = 0
    for cshot in compiled["shots"]:
        approved = shots.get(cshot["shot_id"])
        if cshot["global_start_frame"] != offset:
            err("compiled shot ordering/gap mismatch")
        if approved is not None and cshot["frame_count"] != approved["duration_frames"]:
            err("compiled shot duration mismatch")
        if cshot["shot_id"] in compiled_by_shot:
            err("duplicate compiled shot")
        compiled_by_shot[cshot["shot_id"]] = cshot
        offset += cshot["frame_count"]
    render = bundle["render_manifest.v1"]
    if render["compiled_film_artifact_id"] != compiled["artifact_id"]:
        err("render compiled-film lineage mismatch")
    frames = render["frames"]
    if [frame["frame"] for frame in frames] != list(range(offset)):
        err("render frames must be exact ordered complete set")
    for frame in frames:
        owner = compiled_by_shot.get(frame["shot_id"])
        if owner is None:
            err("render frame shot missing")
        elif not owner["global_start_frame"] <= frame["frame"] < owner["global_start_frame"] + owner["frame_count"]:
            err("render frame wrong shot ownership")

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
    schemas = load_schemas()
    valid = load_json(VALID_PATH)
    invalid = load_json(INVALID_PATH)
    if set(valid) != REQUIRED or set(invalid) != REQUIRED:
        raise ValueError("fixture completeness mismatch")

    canonical: dict[str, dict[str, Any]] = {}
    for name in sorted(REQUIRED):
        document = valid[name]
        found = schema_errors(schemas[name], document)
        if found:
            raise ValueError(f"valid {name} failed: {found[0]}")
        canonical[name] = document
    semantic = semantic_validate_bundle(canonical)
    if semantic:
        raise ValueError(f"valid cross-artifact bundle failed: {semantic}")

    negative_count = 0
    for name in sorted(REQUIRED):
        for case in invalid[name]:
            document = apply_mutations(canonical[name], case["mutations"])
            if case["mode"] == "schema":
                found = schema_errors(schemas[name], document)
                haystack = " ".join(found).lower()
            elif case["mode"] == "semantic":
                mutated = copy.deepcopy(canonical)
                mutated[name] = document
                # Isolate semantic expectations from unrelated schema defects.
                if schema_errors(schemas[name], document):
                    raise ValueError(f"semantic case {name}/{case['name']} violates its schema")
                haystack = " ".join(semantic_validate_bundle(mutated)).lower()
            else:
                raise ValueError(f"unknown fixture mode: {case['mode']}")
            if not haystack:
                raise ValueError(f"invalid {name}/{case['name']} was accepted")
            expected = case["expected"].lower().replace(".", "/")
            if expected not in haystack:
                raise ValueError(f"invalid {name}/{case['name']} failed for wrong reason: {haystack[:300]}")
            negative_count += 1
    return len(schemas), len(canonical), negative_count

def main() -> int:
    schema_count,positive_count,negative_count=validate_all()
    print(f"PASS schemas={schema_count} positive={positive_count} negative={negative_count} semantic_bundle=1")
    return 0
if __name__=="__main__": raise SystemExit(main())
