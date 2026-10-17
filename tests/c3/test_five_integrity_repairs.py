"""C3 H1/H2/M1/H3/H4: deterministic ownership, exact lineage and prompt regressions."""
from __future__ import annotations

import io
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from PIL import Image

from app.animation import service as s, authoring, resolver, generation
from test_authoring_local_assets import (
    client, ok, channel, project, build_story, reserved, _seed_g,
)


def png(rgb=(40, 60, 90)):
    stream=io.BytesIO()
    Image.new("RGB",(32,32),rgb).save(stream,format="PNG")
    return stream.getvalue()


def _version(client,pid,requirement,rgb=(40,60,90)):
    candidate=ok(client.post(f"/api/v1/projects/{pid}/images/import",
        files={"file":("owned.png",png(rgb),"image/png")},
        data={"kind":requirement["kind"],"semantic_key":requirement["semantic_key"],
              "view":requirement["view"]}),201)
    ok(client.post(f"/api/v1/projects/{pid}/assets/{candidate['asset_version_id']}/review",
                   json={"decision":"approved"}))
    return candidate["asset_version_id"]


def _bind(client,pid,requirement,version_id,fingerprint):
    return ok(client.post(f"/api/v1/projects/{pid}/asset-bindings",
        json={"requirement_id":requirement["requirement_id"],"asset_version_id":version_id,
              "expected_fingerprint":fingerprint}))


def _complete(client,tag):
    ch=channel(client,tag)
    pid=project(client,ch,"story")["project_id"]
    build_story(client,pid)
    state=resolver.resolution(pid)
    versions={}
    for row in state["requirements"]:
        req=row["requirement"]
        versions[req["requirement_id"]]=_version(client,pid,req)
        _bind(client,pid,req,versions[req["requirement_id"]],state["requirements_fingerprint"])
    assert resolver.resolution(pid)["resolved_count"]==state["total_count"]
    return pid,state,versions


def test_h1_cancel_before_submitted_never_spends(client,monkeypatch):
    pid,_,_,op=_seed_g(client,monkeypatch,"h1before")
    oid=op["operation_id"]
    assert generation.cancel(pid,oid)["status"]=="cancelled"
    assert generation.cancel(pid,oid)["status"]=="cancelled"
    class Forbidden:
        def submit_image(self,*_):
            pytest.fail("No paid POST allowed after queued cancellation")
    record=generation.advance(pid,oid,client=Forbidden())
    assert record["status"]=="cancelled"
    assert record["error"]["code"]=="CANCELLED_BEFORE_SUBMISSION"
    assert record["task"]["provider_handle_json"] is None


@pytest.mark.parametrize("ack", [True,False])
def test_h1_cancel_during_submit_preserves_exact_ack_or_unknown(client,monkeypatch,ack):
    pid,_,_,op=_seed_g(client,monkeypatch,"h1during"+str(int(ack)))
    oid=op["operation_id"]
    class CancelWhileSending:
        calls=0
        def submit_image(self,payload):
            self.calls+=1
            assert generation.cancel(pid,oid)["status"]=="cancelled"
            if ack:return {"task_id":"abcda123","status":"pending"}
            raise TimeoutError("Provider may have charged but acknowledgment was lost")
    fake=CancelWhileSending()
    first=generation.advance(pid,oid,client=fake)
    assert first["status"]=="cancelled"
    assert first["task"]["provider_handle_json"] == (json.dumps({"task_id":"abcda123"},sort_keys=True,separators=(",",":")) if ack else None)
    assert first["error"]["code"]==("CANCELLED_WITH_PROVIDER_HANDLE" if ack else "CANCELLED_SUBMISSION_UNCERTAIN")
    assert generation.advance(pid,oid,client=fake)["status"]=="cancelled"
    assert fake.calls==1
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as restarted:
        persisted=ok(restarted.get(f"/api/v1/projects/{pid}/generation/operations/{oid}"))
        assert persisted["task"]["provider_handle_json"]==first["task"]["provider_handle_json"]


def test_h1_cancel_during_download_does_not_publish_candidate(client,monkeypatch):
    pid,_,_,op=_seed_g(client,monkeypatch,"h1download")
    oid=op["operation_id"]
    class CancelDuringDownload:
        calls=0
        def submit_image(self,p):self.calls+=1;return {"task_id":"abcdef12","status":"pending"}
        def get_status(self,tid):return {"status":"completed"}
        def get_result(self,tid):return {"results":["http://127.0.0.1:8765/files/out.png"]}
        def download_file(self,url,path,limit):
            assert generation.cancel(pid,oid)["status"]=="cancelled"
            path.write_bytes(png())
    fake=CancelDuringDownload()
    result=generation.advance(pid,oid,client=fake)
    assert result["status"]=="cancelled"
    assert fake.calls==1
    with s.reader() as con:
        count=con.execute("""SELECT COUNT(*) FROM artifacts WHERE kind='asset_source_image.v1'
               AND json_extract(metadata_json,'$.operation_id')=?""",(oid,)).fetchone()[0]
    assert count==0


def test_h2_two_simultaneous_queued_advances_one_paid_post(client,monkeypatch):
    pid,_,_,op=_seed_g(client,monkeypatch,"h2queued")
    oid=op["operation_id"]
    entered,release=Event(),Event()
    class HoldSubmit:
        calls=0
        def submit_image(self,payload):
            self.calls+=1
            entered.set()
            assert release.wait(12)
            return {"task_id":"1234abcd","status":"pending"}
        def get_status(self,tid):return {"status":"pending"}
    fake=HoldSubmit()
    with ThreadPoolExecutor(max_workers=2) as pool:
        first=pool.submit(generation.advance,pid,oid,fake)
        assert entered.wait(12)
        second=pool.submit(generation.advance,pid,oid,fake)
        assert second.result(timeout=12)["status"]=="running"
        release.set()
        assert first.result(timeout=12)["status"]=="running"
    assert fake.calls==1


def test_h2_concurrent_poll_and_crash_after_candidate_reuses_exact_id(client,monkeypatch):
    pid,_,_,op=_seed_g(client,monkeypatch,"h2poll")
    oid=op["operation_id"]
    entered,release=Event(),Event()
    class Fake:
        submits=0
        waiting=False
        def submit_image(self,p):
            self.submits+=1
            return {"task_id":"aaaa1234","status":"pending"}
        def get_status(self,tid):
            if self.waiting:
                entered.set()
                assert release.wait(12)
            return {"status":"completed" if self.waiting else "pending"}
        def get_result(self,tid):return {"results":["http://127.0.0.1:8765/files/out.png"]}
        def download_file(self,url,path,max_bytes):path.write_bytes(png())
    fake=Fake()
    assert generation.advance(pid,oid,client=fake)["status"]=="running"
    fake.waiting=True
    with ThreadPoolExecutor(max_workers=2) as pool:
        first=pool.submit(generation.advance,pid,oid,fake)
        assert entered.wait(12)
        second=pool.submit(generation.advance,pid,oid,fake)
        assert second.result(timeout=12)["status"]=="running"
        release.set()
        completed=first.result(timeout=12)
    assert completed["status"]=="completed",completed
    candidate_id=completed["result"]["candidate"]["asset_version_id"]
    assert generation.advance(pid,oid,client=fake)["result"]["candidate"]["asset_version_id"]==candidate_id
    assert fake.submits==1
    with s.reader() as con:
        assert con.execute("""SELECT COUNT(*) FROM artifacts WHERE kind='asset_version.v1'
                  AND json_extract(metadata_json,'$.operation_id')=?""",(oid,)).fetchone()[0]==1


def test_h2_crash_after_materialization_recovers_without_new_candidate(client,monkeypatch):
    pid,_,_,op=_seed_g(client,monkeypatch,"h2crash")
    oid=op["operation_id"]
    class Fake:
        submits=0
        def submit_image(self,p):self.submits+=1;return {"task_id":"dead1234","status":"pending"}
        def get_status(self,tid):return {"status":"completed"}
        def get_result(self,tid):return {"results":["http://127.0.0.1:8765/files/out.png"]}
        def download_file(self,url,path,max_bytes):path.write_bytes(png())
    fake=Fake()
    original=generation.transition
    crashed=False
    def injected(con,opid,status,task,*args,**kwargs):
        nonlocal crashed
        if status=="completed" and not crashed:
            crashed=True
            raise SystemExit("power cut after committed candidate before terminal update")
        return original(con,opid,status,task,*args,**kwargs)
    monkeypatch.setattr(generation,"transition",injected)
    with pytest.raises(SystemExit):
        generation.advance(pid,oid,client=fake)
    with s.reader() as con:
        prev=con.execute("""SELECT v.asset_version_id FROM asset_versions v
            JOIN artifacts ar ON ar.artifact_id=v.artifact_id WHERE
            json_extract(ar.metadata_json,'$.operation_id')=?""",(oid,)).fetchone()[0]
    monkeypatch.setattr(generation,"transition",original)
    resumed=generation.advance(pid,oid,client=fake)
    assert resumed["status"]=="completed"
    assert resumed["result"]["candidate"]["asset_version_id"]==prev
    assert fake.submits==1
    with s.reader() as con:
        assert con.execute("""SELECT COUNT(*) FROM artifacts WHERE kind='asset_version.v1'
            AND json_extract(metadata_json,'$.operation_id')=?""",(oid,)).fetchone()[0]==1


def test_m1_pin_swap_during_file_publication_rejected_atomic(client,monkeypatch):
    pid,state,versions=_complete(client,"m1swap")
    req=state["requirements"][0]["requirement"]
    original=versions[req["requirement_id"]]
    replacement=_version(client,pid,req,(9,8,7))
    original_publish=s.document_publish
    def swap_during_publish(document,relative,callback,**kwargs):
        if "/resolutions/" not in relative:
            return original_publish(document,relative,callback,**kwargs)
        def wrapped(con,digest,size):
            # Exactly same pin COUNT. Mutation and snapshot check share writer.
            con.execute("""UPDATE project_asset_bindings SET asset_version_id=?
              WHERE project_id=? AND usage_key=?""",(replacement,pid,req["requirement_id"]))
            return callback(con,digest,size)
        return original_publish(document,relative,wrapped,**kwargs)
    monkeypatch.setattr(s,"document_publish",swap_during_publish)
    with pytest.raises(s.DomainError) as err:
        resolver.publish_resolution(pid)
    assert err.value.code=="STALE_HEAD"
    with s.reader() as con:
        assert con.execute("""SELECT COUNT(*) FROM artifacts
                    WHERE project_id=? AND kind='asset_resolution.v1'""",(pid,)).fetchone()[0]==0
        pin=con.execute("""SELECT asset_version_id FROM project_asset_bindings
            WHERE project_id=? AND usage_key=?""",(pid,req["requirement_id"])).fetchone()[0]
        assert pin==original


def test_h4_restore_A_B_A_reuses_artifact_and_activates_monotonic_head(client):
    pid,state,versions=_complete(client,"h4reuse")
    actor=next(x["requirement"] for x in state["requirements"] if x["requirement"]["kind"]=="actor")
    key=actor["requirement_id"]
    second=_version(client,pid,actor,(1,2,3))
    first=resolver.publish_resolution(pid)
    assert first["kind"]=="asset_resolution.v1"
    with s.reader() as con:
        first_rev=con.execute("SELECT revision FROM project_stage_heads WHERE project_id=? AND stage_key='resolver'",(pid,)).fetchone()[0]
        binding=con.execute("SELECT binding_id FROM project_asset_bindings WHERE project_id=? AND usage_key=?",(pid,key)).fetchone()[0]
    resolver.unbind(pid,binding,state["requirements_fingerprint"])
    _bind(client,pid,actor,second,state["requirements_fingerprint"])
    b=resolver.publish_resolution(pid)
    assert b["artifact_id"]!=first["artifact_id"]
    with s.reader() as con:
        new=con.execute("SELECT binding_id FROM project_asset_bindings WHERE project_id=? AND usage_key=?",(pid,key)).fetchone()[0]
    resolver.unbind(pid,new,state["requirements_fingerprint"])
    _bind(client,pid,actor,versions[key],state["requirements_fingerprint"])
    restored=resolver.publish_resolution(pid)
    assert restored["artifact_id"]==first["artifact_id"]
    with s.reader() as con:
        head=con.execute("""SELECT artifact_id,revision,approval_status
              FROM project_stage_heads WHERE project_id=? AND stage_key='resolver'""",(pid,)).fetchone()
        count=con.execute("""SELECT COUNT(*) FROM artifacts WHERE kind='asset_resolution.v1'
                     AND project_id=?""",(pid,)).fetchone()[0]
    assert head["artifact_id"]==first["artifact_id"] and head["approval_status"]=="approved"
    assert head["revision"]==first_rev+2 and count==2
    assert resolver.publish_resolution(pid)["artifact_id"]==first["artifact_id"]
    with s.reader() as con:
        assert con.execute("SELECT revision FROM project_stage_heads WHERE project_id=? AND stage_key='resolver'",(pid,)).fetchone()[0]==head["revision"]
    from app.animation.service import workflow
    assert next(x for x in workflow(pid)["stages"] if x["stage_key"]=="resolver")["readiness"]=="approved"


def test_h3_authoritative_copied_prompt_holds_source_and_analysis(client):
    ch=channel(client,"h3prompt")
    pid=project(client,ch,"story")["project_id"]
    prefix=f"/api/v1/projects/{pid}/authoring"
    topic=ok(client.post(prefix+"/topic-ideas/prompt",json={}),201)
    copied=json.loads(topic["prompt_text"].split("=== BEGIN AUTHORING PACKAGE JSON ===")[1]
                      .split("=== END AUTHORING PACKAGE JSON ===")[0])
    assert copied["dna_metadata"]["sha256"]==topic["dna_metadata"]["sha256"]
    assert copied["dna_metadata"]["artifact_id"]==topic["dna_metadata"]["artifact_id"]
    ideas,_=reserved(client,pid,"topic-ideas",
        lambda p:{"channel_dna_artifact_id":p["dna_metadata"]["artifact_id"],
                  "channel_dna_hash":p["dna_metadata"]["sha256"],
                  "ideas":[{"idea_id":"idea_one","title":"Some ideas","premise":"An imagined animated event"}]})
    script_package=ok(client.post(prefix+"/script/prompt",json={}),201)
    assert ideas["sha256"] in script_package["prompt_text"]
    assert ideas["artifact_id"] in script_package["prompt_text"]
    script,_=reserved(client,pid,"script",
        lambda p:{"topic_ideas_artifact_id":ideas["artifact_id"],"selected_idea_id":"idea_one",
                  "full_text":"Hello!","sections":[{"section_id":"section_one","start_char":0,
                                                   "end_char":6,"text":"Hello!"}]})
    analysis,_=reserved(client,pid,"script-analysis",
        lambda p:{"script_artifact_id":script["artifact_id"],"entities":[],
                  "continuity_notes":["Keep actor world states aligned"]})
    shot=ok(client.post(prefix+"/shot-plan/prompt",json={}),201)
    full=shot["prompt_text"]
    assert script["artifact_id"] in full and script["sha256"] in full
    assert analysis["artifact_id"] in full and analysis["sha256"] in full
    assert "24..720" in full and "half-open" in full
    copied=json.loads(full.split("=== BEGIN AUTHORING PACKAGE JSON ===")[1]
                      .split("=== END AUTHORING PACKAGE JSON ===")[0])
    assert copied["analysis_metadata"]["artifact_id"]==analysis["artifact_id"]
    assert copied["reserved_fields"]==shot["reserved_fields"]
    assert copied["source_metadata"]["sha256"]==script["sha256"]
