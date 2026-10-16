from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
REGISTER=ROOT/"contracts/animation/api/endpoints.json"
DOC=ROOT/"docs/architecture/API_CONTRACTS.md"
STAGES=["authoring","resolver","generation","rigging","director","motion","delivery"]
FORBIDDEN=("scene_breakdown","beat_timing","voice_first","visual_plan","render_graph","legacy_mode")

def rows(): return json.loads(REGISTER.read_text(encoding="utf-8"))

def lint_endpoint_rows(endpoints) -> list[str]:
    errors=[];keys=[(row.get("method"),row.get("path")) for row in endpoints]
    if len(keys)!=len(set(keys)): errors.append("duplicate method/path")
    accepted="\n".join(json.dumps(row) for row in endpoints if row.get("contract_status")=="ACCEPTED").lower()
    if any(value in accepted for value in FORBIDDEN): errors.append("legacy active authority")
    dna=next((row for row in endpoints if row.get("path","").endswith("/dna") and row.get("method")=="PUT"),None)
    if not dna or "expected_head_revision" not in dna.get("precondition",""): errors.append("DNA CAS precondition missing")
    return errors

def test_endpoint_register_is_unique_and_complete() -> None:
    endpoints=rows();keys=[(row["method"],row["path"]) for row in endpoints]
    assert len(keys)==len(set(keys))
    required={"method","path","phase","owner","contract_status","request_dto","response_dto","success","errors","precondition","idempotency","authority","readiness"}
    assert all(set(row)==required and all(value not in ("",None) for value in row.values()) for row in endpoints)
    assert all("..." not in row["path"] and row["path"].startswith(("/health","/api/v1/")) for row in endpoints)
    assert all(row["method"] in {"GET","POST","PUT","PATCH","DELETE"} for row in endpoints)

def test_c2_is_accepted_and_future_routes_are_only_proposed() -> None:
    for row in rows():
        assert row["contract_status"] == ("ACCEPTED" if row["phase"]=="C2" else "PROPOSED")
    assert not any(row["response_dto"] in {"Any","TBD","None"} and row["method"]!="GET" for row in rows())

def test_exact_seven_stages_and_no_legacy_active_authority() -> None:
    text=DOC.read_text(encoding="utf-8")
    assert " → ".join(STAGES) in text
    accepted="\n".join(json.dumps(row) for row in rows() if row["contract_status"]=="ACCEPTED").lower()
    for forbidden in FORBIDDEN:
        assert forbidden not in accepted
    assert lint_endpoint_rows(rows()) == []

def test_cas_idempotency_and_invalidation_are_explicit() -> None:
    text=DOC.read_text(encoding="utf-8")
    for phrase in ("expected_head_revision","STALE_HEAD","IDEMPOTENCY_CONFLICT","narration_identity_hash","Voice is always downstream"):
        assert phrase in text

def test_source_revision_precondition_mutation_would_fail() -> None:
    mutated=[dict(row) for row in rows()]
    dna=next(row for row in mutated if row["path"].endswith("/dna") and row["method"]=="PUT")
    dna["precondition"]="none"
    assert "DNA CAS precondition missing" in lint_endpoint_rows(mutated)

def test_voice_first_injection_is_detected() -> None:
    mutated=[dict(row) for row in rows()]
    mutated[0]["authority"]="voice_first compatibility"
    assert "legacy active authority" in lint_endpoint_rows(mutated)
