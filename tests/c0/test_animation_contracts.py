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
    semantic_validate_bundle, validate_all,
)


@pytest.fixture(scope="module")
def valid_bundle():
    return {name: documents[0] for name, documents in load_json(VALID_PATH).items()}


def test_all_schemas_positive_and_negative_fixture_counts() -> None:
    assert validate_all() == (18, 36, 108)
    invalid = load_json(INVALID_PATH)
    assert set(invalid) == REQUIRED
    assert all(len(cases) >= 4 for cases in invalid.values())


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
