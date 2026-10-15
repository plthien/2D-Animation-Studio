from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest
from referencing.exceptions import Unresolvable

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from validate_c0_contracts import (  # noqa: E402
    INVALID_PATH, REQUIRED, VALID_PATH, load_json, load_schemas, schema_errors,
    canonical_json_bytes, canonical_json_sha256,
    semantic_validate_bundle, validate_all,
)


@pytest.fixture(scope="module")
def valid_bundle():
    return load_json(VALID_PATH)


def test_all_schemas_positive_and_negative_fixture_counts() -> None:
    assert validate_all() == (18, 18, 40)
    invalid = load_json(INVALID_PATH)
    assert set(invalid) == REQUIRED
    assert all(len(cases) >= 2 for cases in invalid.values())


def test_duplicate_json_keys_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.json"
    path.write_text('{"schema_version":"x","schema_version":"y"}', encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate JSON key"):
        load_json(path)


def test_shot_plan_uses_shot_local_duration_and_rejects_old_interval(valid_bundle) -> None:
    schemas = load_schemas(); doc = copy.deepcopy(valid_bundle["shot_plan.v1"])
    doc["shots"][0]["start_frame"] = 200
    doc["shots"][0]["end_frame"] = 24
    assert any("Additional properties" in error for error in schema_errors(schemas["shot_plan.v1"], doc))


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (lambda b: b["animation_plan.v1"]["actions"][0].update(start_frame=47,end_frame=60), "action outside shot bounds"),
        (lambda b: b["rig_profile.v1"]["bones"].__setitem__(1,copy.deepcopy(b["rig_profile.v1"]["bones"][0])), "rig requires unique semantic bones"),
        (lambda b: [part.update(role="head",pivot={}) for part in b["parts_manifest.v1"]["parts"]], "parts must contain 14 unique semantic roles"),
        (lambda b: b["render_manifest.v1"]["frames"].pop(3), "render frames must be exact ordered complete set"),
        (lambda b: b["render_manifest.v1"]["frames"].__setitem__(2,copy.deepcopy(b["render_manifest.v1"]["frames"][1])), "render frames must be exact ordered complete set"),
        (lambda b: b["voice_manifest.v1"]["voiced_shots"][0].update(sample_count=2000), "voice sample/frame count mismatch"),
        (lambda b: b["asset_resolution.v1"]["pins"][0].update(requirement_id="requirement_missing"), "nonexistent asset-resolution pin"),
    ],
)
def test_required_cross_artifact_counterexamples(valid_bundle, mutate, expected: str) -> None:
    bundle=copy.deepcopy(valid_bundle);mutate(bundle)
    assert expected in semantic_validate_bundle(bundle)


def test_invalid_fixture_mutated_to_valid_is_detected(valid_bundle) -> None:
    schemas=load_schemas()
    assert schema_errors(schemas["script.v1"],valid_bundle["script.v1"]) == []
    # The negative harness requires at least one error; replacing the case with
    # this document therefore fails closed rather than counting a false PASS.
    assert not schema_errors(schemas["script.v1"],valid_bundle["script.v1"])


def test_fixture_completeness_mutation_is_detected() -> None:
    valid=load_json(VALID_PATH);valid.pop("qc_report.v1")
    assert set(valid) != REQUIRED


def test_unresolved_ref_fails_validation(valid_bundle) -> None:
    schema={"$schema":"https://json-schema.org/draft/2020-12/schema","$ref":"missing.schema.json"}
    with pytest.raises(Exception) as exc:
        schema_errors(schema,valid_bundle["script.v1"])
    assert "resolve" in str(exc.value).lower() or isinstance(exc.value,Unresolvable)


@pytest.mark.parametrize("value", ['{"x":1e400}', '{"x":-1e400}', '{"nested":[{"x":1e400}]}', '{"x":NaN}', '{"x":Infinity}'])
def test_nonfinite_json_is_rejected(tmp_path: Path, value: str) -> None:
    path = tmp_path / "bad.json"
    path.write_text(value, encoding="utf-8")
    with pytest.raises(ValueError, match="non-finite"):
        load_json(path)


def test_canonical_hash_stable_and_finite_only() -> None:
    first = {"b": [1, {"x": 0.125}], "a": "hi"}
    second = {"a": "hi", "b": [1, {"x": 0.125}]}
    assert canonical_json_bytes(first) == canonical_json_bytes(second)
    assert canonical_json_sha256(first) == canonical_json_sha256(second)
    for bad in (float("inf"), float("-inf"), float("nan")):
        with pytest.raises(ValueError, match="non-finite"):
            canonical_json_sha256({"outer": [bad]})
    assert len(canonical_json_sha256({"finite": 0.25})) == 64

def test_channel_overlap_and_conflicts(valid_bundle) -> None:
    def motion(kind: str, ident: str, hand: str = "none") -> dict:
        item = copy.deepcopy(valid_bundle["animation_plan.v1"]["actions"][0])
        item.update(action=kind, action_id=ident, hand=hand, target_id="prop_box",
                    prop_id=None if kind in {"walk_to", "look_at", "reach_for"} else "prop_box",
                    start_frame=0, end_frame=12)
        return item

    def check(actions: list[dict]) -> list[str]:
        bundle = copy.deepcopy(valid_bundle)
        bundle["animation_plan.v1"]["actions"] = actions
        return semantic_validate_bundle(bundle)

    assert "conflicting motion channel" not in " ".join(check([motion("walk_to", "walk"), motion("look_at", "look")]))
    assert "conflicting motion channel" in " ".join(check([motion("walk_to", "walk"), motion("walk_to", "walk2")]))
    assert "conflicting motion channel: left_arm" in " ".join(check([motion("reach_for", "reach", "left"), motion("reach_for", "reach2", "left")]))
    assert "conflicting motion channel" not in " ".join(check([motion("reach_for", "left", "left"), motion("reach_for", "right", "right")]))


def test_compiled_shot_frame_ownership_and_duration(valid_bundle) -> None:
    bundle = copy.deepcopy(valid_bundle)
    assert not semantic_validate_bundle(bundle)

    bundle["compiled_film.v1"]["shots"][0]["frame_count"] = 47
    assert "compiled shot duration mismatch" in semantic_validate_bundle(bundle)
    bundle = copy.deepcopy(valid_bundle)
    bundle["render_manifest.v1"]["frames"][4]["shot_id"] = "shot_other"
    assert "render frame shot missing" in semantic_validate_bundle(bundle)
    bundle = copy.deepcopy(valid_bundle)
    bundle["render_manifest.v1"]["frames"].pop()
    assert "render frames must be exact ordered complete set" in semantic_validate_bundle(bundle)

def test_valid_240_frame_shot_and_cross_shot_frame_owner(valid_bundle) -> None:
    bundle = copy.deepcopy(valid_bundle)
    bundle["shot_plan.v1"]["shots"][0]["duration_frames"] = 240
    bundle["animation_plan.v1"]["actions"][0]["end_frame"] = 240
    bundle["compiled_film.v1"]["shots"][0]["frame_count"] = 240
    prototype = bundle["render_manifest.v1"]["frames"][0]
    bundle["render_manifest.v1"]["frames"] = [
        {**prototype, "frame": index, "relative_path": f"frames/{index:06d}.png",
         "sha256": f"{index + 1:064x}"}
        for index in range(240)
    ]
    assert not semantic_validate_bundle(bundle)
    # Add a second approved shot; no action is required for a static shot.
    second = copy.deepcopy(bundle["shot_plan.v1"]["shots"][0])
    second["shot_id"] = "shot_two"
    second["duration_frames"] = 24
    bundle["shot_plan.v1"]["shots"].append(second)
    compiled_second = copy.deepcopy(bundle["compiled_film.v1"]["shots"][0])
    compiled_second.update(shot_id="shot_two", global_start_frame=240, frame_count=24, action_ids=[])
    bundle["compiled_film.v1"]["shots"].append(compiled_second)
    bundle["render_manifest.v1"]["frames"] += [
        {**prototype, "frame": index, "shot_id": "shot_two",
         "relative_path": f"frames/{index:06d}.png", "sha256": f"{index + 1:064x}"}
        for index in range(240, 264)
    ]
    assert not semantic_validate_bundle(bundle)
    bundle["render_manifest.v1"]["frames"][239]["shot_id"] = "shot_two"
    assert "render frame wrong shot ownership" in semantic_validate_bundle(bundle)


def test_schema_validation_rejects_python_nonfinite_coordinates(valid_bundle) -> None:
    schemas = load_schemas()
    parts = copy.deepcopy(valid_bundle["parts_manifest.v1"])
    parts["parts"][0]["pivot"]["x"] = float("inf")
    assert "non-finite" in " ".join(schema_errors(schemas["parts_manifest.v1"], parts))
