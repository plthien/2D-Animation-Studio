"""C2 correctness gates: real API, schema, replay, CAS and legacy isolation."""
from __future__ import annotations

import concurrent.futures
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.animation import service
from app.animation.database import APPLICATION_TABLES
from app.main import app

STAGES = ("authoring", "resolver", "generation", "rigging", "director", "motion", "delivery")


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///" + (tmp_path / "animation.db").as_posix())
    monkeypatch.setenv("ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("AUTO_APPLY_MIGRATIONS", "true")
    with TestClient(app) as c:
        yield c


def data(response, code=200):
    assert response.status_code == code, response.text
    value = response.json()
    assert set(value) == {"data", "meta"}
    assert value["meta"]["schema_version"] == "api.v1"
    return value["data"]


def error(response, status, code):
    assert response.status_code == status, response.text
    value = response.json()
    assert value["error"]["code"] == code
    assert value["error"]["request_id"].startswith("req_")


def new_channel(client, name="Animation Alpha", slug="alpha", key="channel-1"):
    return data(client.post("/api/v1/channels", json={"name":name,"slug":slug},
                            headers={"Idempotency-Key":key}), 201)


def dna():
    return {"schema_version":"channel_dna.v2",
            "identity":{"name":"Animation Alpha","audience":"English entertainment viewers"},
            "visual":{"style":"Hand-drawn flat 2D with uneven outlines","palette":["#123456","#F0E0D0"]},
            "performance":{"tone":"expressive and witty","motion_density":"medium"},
            "narration":{"language":"en","voice_character":"friendly male narrator"}}


def publish_dna(client, channel, key="dna-1", expected_revision=None, expected_aid=None):
    return data(client.put(
        f"/api/v1/channels/{channel['channel_id']}/dna",
        json={"channel_dna":dna(), "expected_head_revision":expected_revision,
              "expected_head_artifact_id":expected_aid},
        headers={"Idempotency-Key":key}), 201)


def approve(client, channel, candidate, expected_revision=None):
    return data(client.post(
        f"/api/v1/channels/{channel['channel_id']}/dna/{candidate['artifact_id']}/approve",
        json={"expected_head_revision":expected_revision, "expected_sha256":candidate["sha256"],
              "actor":"qa", "reviewed_at":"2026-10-16T00:00:00Z"}))


def test_openapi_exact_19_and_no_legacy(client):
    import json
    from pathlib import Path
    registry=json.loads((Path(__file__).resolve().parents[2]/
                         "contracts/animation/api/endpoints.json").read_text(encoding="utf-8"))
    accepted={(row["method"],row["path"]) for row in registry if row["contract_status"]=="ACCEPTED"}
    actual={(method.upper(),path) for path,definition in app.openapi()["paths"].items()
            for method in definition if method.lower() in {"get","post","put","patch","delete"}}
    assert len(accepted)==19
    assert actual==accepted
    for row in registry:
        if row["contract_status"]=="PROPOSED":
            assert (row["method"],row["path"]) not in actual
    assert data(client.get("/health"))["status"]=="ok"
    assert data(client.get("/api/v1/system"))["animation_generation_ready"] is False
    for path in ("/api/v4/voice/generate","/api/v4/scene-assets","/api/v1/projects/p/voice/generate"):
        assert client.post(path, json={}).status_code==404


def test_channel_dna_project_restart_and_replay(client):
    ch = new_channel(client)
    assert new_channel(client)==ch
    error(client.post("/api/v1/channels",json={"name":"different","slug":"different"},
                      headers={"Idempotency-Key":"channel-1"}),409,"IDEMPOTENCY_CONFLICT")
    error(client.post("/api/v1/channels",json={"name":"another","slug":"alpha"},
                      headers={"Idempotency-Key":"channel-2"}),409,"DUPLICATE_SLUG")
    head=data(client.get(f"/api/v1/channels/{ch['channel_id']}/dna"))
    assert head["head_revision"] is None
    candidate=publish_dna(client,ch)
    assert candidate["revision"]==1 and candidate["approval_status"]=="draft"
    assert publish_dna(client,ch)==candidate
    error(client.put(f"/api/v1/channels/{ch['channel_id']}/dna",json={
          "channel_dna":{**dna(),"identity":{"name":"changed","audience":"viewers"}},
          "expected_head_revision":None,"expected_head_artifact_id":None},
          headers={"Idempotency-Key":"dna-1"}),409,"IDEMPOTENCY_CONFLICT")
    accepted=approve(client,ch,candidate)
    assert accepted["head_artifact_id"]==candidate["artifact_id"]
    assert accepted["head_revision"]==1
    assert accepted["channel"]["visual_style_hash"] != "0"*64
    assert approve(client,ch,candidate)["head_artifact_id"]==candidate["artifact_id"]
    project=data(client.post("/api/v1/projects",json={
        "channel_id":ch["channel_id"],"name":"Pilot","slug":"pilot"},
        headers={"Idempotency-Key":"project-1"}),201)
    wf=data(client.get(f"/api/v1/projects/{project['project_id']}/workflow"))
    assert tuple(s["stage_key"] for s in wf["stages"])==STAGES
    assert len(wf["stages"])==7
    assert wf["stages"][0]["readiness"]=="blocked"
    assert "REQUIRES_C3_AUTHORING" in wf["stages"][0]["blocker_codes"]
    for stage in wf["stages"][1:]:
        assert stage["readiness"]=="blocked" and stage["blocker_codes"]
    assert all(s["head_revision"]==0 for s in wf["stages"])
    assert data(client.post("/api/v1/projects",json={
        "channel_id":ch["channel_id"],"name":"Pilot","slug":"pilot"},
        headers={"Idempotency-Key":"project-1"}),201)==project
    assert data(client.get(f"/api/v1/projects/{project['project_id']}"))==project
    assert data(client.get("/api/v1/projects",params={"channel_id":ch["channel_id"]}))["items"]==[project]
    assert data(client.get("/api/v1/jobs",params={"project_id":project["project_id"]}))["items"]==[]
    error(client.get("/api/v1/jobs/nonexistent",params={"project_id":project["project_id"]}),404,"NOT_FOUND")
    meta=data(client.get(f"/api/v1/artifacts/{candidate['artifact_id']}",params={"channel_id":ch["channel_id"]}))
    assert meta["sha256"]==candidate["sha256"]
    error(client.get(f"/api/v1/artifacts/{candidate['artifact_id']}",params={"channel_id":"ch_another"}),404,"NOT_FOUND")
    # Restart the actual database connection and assert both identities still exist.
    with service.reader() as con:
        assert con.execute("PRAGMA foreign_key_check").fetchall()==[]
        assert con.execute("SELECT COUNT(*) FROM project_stage_heads").fetchone()[0]==7
        assert con.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchone()[0]==15
    assert data(client.get(f"/api/v1/projects/{project['project_id']}/workflow"))==wf


def test_stale_approval_and_candidate_immutability(client):
    ch = new_channel(client)
    draft1=publish_dna(client,ch,key="dna-1")
    draft2=publish_dna(client,ch,key="dna-2")
    assert draft2["revision"]==2
    approve(client,ch,draft1)
    error(client.post(f"/api/v1/channels/{ch['channel_id']}/dna/{draft2['artifact_id']}/approve",
        json={"expected_head_revision":None,"expected_sha256":draft2["sha256"],
              "actor":"qa","reviewed_at":"2026-10-16T00:00:00Z"}),409,"STALE_HEAD")
    assert data(client.get(f"/api/v1/artifacts/{draft2['artifact_id']}",params={"channel_id":ch["channel_id"]}))["approval_status"]=="draft"
    assert data(client.get(f"/api/v1/artifacts/{draft1['artifact_id']}",params={"channel_id":ch["channel_id"]}))["approval_status"]=="approved"


def test_archive_and_validation(client):
    ch=new_channel(client)
    error(client.get("/api/v1/channels",params={"limit":0}),422,"VALIDATION_FAILED")
    error(client.get("/api/v1/projects",params={}),422,"VALIDATION_FAILED")
    error(client.post("/api/v1/channels",json={"name":"","slug":"xx"},
                      headers={"Idempotency-Key":"bad"}),422,"VALIDATION_FAILED")
    error(client.post("/api/v1/channels",json={"name":"x","slug":"x"},
                      headers={}),422,"VALIDATION_FAILED")
    res=data(client.request("DELETE", f"/api/v1/channels/{ch['channel_id']}",
                  json={"expected_updated_at":ch["updated_at"]}))
    assert res["status"]=="archived"
    repeated=data(client.request("DELETE",f"/api/v1/channels/{ch['channel_id']}",
                    json={"expected_updated_at":ch["updated_at"]}))
    assert repeated["status"]=="archived"
    error(client.post("/api/v1/projects",json={"channel_id":ch["channel_id"],
                      "name":"x","slug":"x"},headers={"Idempotency-Key":"x"}),409,"OWNERSHIP_CONFLICT")


def test_origin_and_host_rejection(client):
    error(client.get("/health",headers={"Origin":"https://attacker.example"}),403,"ORIGIN_REJECTED")
    error(client.get("/health",headers={"host":"attacker.example"}),403,"LOCAL_ONLY")


def test_preflushed_sqlalchemy_transaction_conflict(client, tmp_path):
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session
    eng=create_engine("sqlite:///" + (tmp_path/"other.db").as_posix())
    with eng.begin() as c:
        c.execute(text("CREATE TABLE scratch (id INTEGER PRIMARY KEY)"))
    with Session(eng) as session:
        session.execute(text("INSERT INTO scratch (id) VALUES (1)"))
        session.flush()
        assert session.in_transaction()
        with pytest.raises(service.DomainError) as got:
            service.document_publish({"test":True},"transaction-owner-attempt.json",lambda *_: None,session=session)
        assert got.value.code=="TRANSACTION_OWNERSHIP_CONFLICT"
    eng.dispose()
    assert not (service.artifact_root() / "transaction-owner-attempt.json").exists()


def test_artifact_path_rejects_traversal_and_symlinks(client,tmp_path):
    with pytest.raises(service.DomainError):
        service.bounded_path("../escape.txt")
    with pytest.raises(service.DomainError):
        service.bounded_path("/root/outside.txt")
    root=service.artifact_root()
    external=tmp_path/"other"
    external.mkdir()
    link=root/"link"
    try:link.symlink_to(external,target_is_directory=True)
    except (OSError,NotImplementedError):pytest.skip("Symlink privilege unavailable")
    with pytest.raises(service.DomainError):
        service.bounded_path("link/escape.json")


def test_scope_required_for_artifact_and_job(client):
    ch = new_channel(client)
    candidate = publish_dna(client, ch)
    error(client.get(f"/api/v1/artifacts/{candidate['artifact_id']}"),422,"VALIDATION_FAILED")
    error(client.get("/api/v1/jobs/example"),422,"VALIDATION_FAILED")
    error(client.get(f"/api/v1/artifacts/{candidate['artifact_id']}",
                     params={"channel_id":"ch_other"}),404,"NOT_FOUND")


def test_independent_connection_approval_cas_winner_and_loser(client):
    from concurrent.futures import ThreadPoolExecutor
    ch = new_channel(client)
    first=publish_dna(client,ch,key="first")
    second=publish_dna(client,ch,key="second")
    def try_approve(candidate):
        try:
            return service.approve_dna(
                ch["channel_id"],candidate["artifact_id"],expected_revision=None,
                expected_sha=candidate["sha256"],actor="qa",reviewed_at="2026-10-16T00:00:00Z")
        except service.DomainError as exc:
            return exc.code
    with ThreadPoolExecutor(max_workers=2) as executor:
        results=list(executor.map(try_approve,[first,second]))
    assert sum(isinstance(r,dict) for r in results)==1
    assert results.count("STALE_HEAD")==1
    head=data(client.get(f"/api/v1/channels/{ch['channel_id']}/dna"))
    assert head["head_artifact_id"] in {first["artifact_id"],second["artifact_id"]}
    loser_id=next(x["artifact_id"] for x in (first,second) if x["artifact_id"]!=head["head_artifact_id"])
    loser=data(client.get(f"/api/v1/artifacts/{loser_id}",
                          params={"channel_id":ch["channel_id"]}))
    assert loser["approval_status"]=="draft"
    # Both attempts' immutable draft bytes remain intact, no loser deleted winner.
    for item in (first,second):
        path=service.bounded_path(item["relative_artifact_handle"])
        assert service.filehash(path)==(item["sha256"],item["byte_size"])


def test_db_cross_channel_composite_ownership_fk(client):
    import sqlite3
    left = new_channel(client, name="Left",slug="left",key="left")
    right = new_channel(client,name="Right",slug="right",key="right")
    project=data(client.post("/api/v1/projects",json={
        "channel_id":left["channel_id"],"name":"Foreign Key Project","slug":"fk-test"},
        headers={"Idempotency-Key":"fk-project"}),201)
    with pytest.raises(sqlite3.IntegrityError):
        with service.writer() as con:
            service.add_artifact(
                con,aid=service.uid("ar"),channel_id=right["channel_id"],
                project_id=project["project_id"],kind="test.ownership.v1",
                schema="test.ownership.v1",logical="cross-channel",
                revision=1,status="draft",checksum="0"*64,size=0,
                relative="test/cross-channel.json",metadata={})
    with service.reader() as con:
        assert con.execute("PRAGMA foreign_key_check").fetchall()==[]
        assert con.execute(
            "SELECT COUNT(*) FROM artifacts WHERE logical_key='cross-channel'"
        ).fetchone()[0]==0


def test_failed_publish_rolls_back_owned_file(client):
    ch = new_channel(client)
    aid = service.uid("ar")
    relative=f"channels/{ch['channel_id']}/failure/{aid}.json"
    def callback(con, checksum, size):
        service.add_artifact(
            con,aid=aid,channel_id=ch["channel_id"],project_id=None,
            kind="platform.test.v1",schema="platform.test.v1",
            logical="rollback",revision=1,status="draft",
            checksum=checksum,size=size,relative=relative,metadata={})
        # Force a database constraint error after the metadata insert.
        con.execute("INSERT INTO channels (channel_id) VALUES ('bad')")
    with pytest.raises(Exception):
        service.document_publish({"hello":"world"},relative,callback)
    assert not service.bounded_path(relative).exists()
    with service.reader() as con:
        assert not con.execute("SELECT 1 FROM artifacts WHERE artifact_id=?",(aid,)).fetchone()


def test_bounded_publication_prevents_unbounded_json_work(client):
    ch=new_channel(client)
    relative=f"channels/{ch['channel_id']}/oversized.json"
    with pytest.raises(service.DomainError) as got:
        service.document_publish({"huge":"X"*1_048_576},relative,lambda *_:None)
    assert got.value.code=="IMPORT_TOO_LARGE"
    assert not service.bounded_path(relative).exists()
