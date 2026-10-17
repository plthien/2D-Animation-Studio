"""Focused C3 authoring/resolver/local file acceptance on real disposable SQLite."""
import copy
import io
from pathlib import Path
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from app.main import app
from app.animation import service as s

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv("DATABASE_URL","sqlite:///"+(tmp_path/"animation.db").as_posix())
    monkeypatch.setenv("ARTIFACT_ROOT",str(tmp_path/"artifacts"))
    monkeypatch.setenv("AUTO_APPLY_MIGRATIONS","true")
    with TestClient(app) as http:
        yield http

def ok(r,status=200):
    assert r.status_code==status,r.text
    return r.json()["data"]

def channel(client,key):
    ch=ok(client.post("/api/v1/channels",json={"name":key,"slug":key},
        headers={"Idempotency-Key":key}),201)
    doc={"schema_version":"channel_dna.v2",
         "identity":{"name":"Animation","audience":"Viewers"},
         "visual":{"style":"2D","palette":["#aabbcc"]},
         "performance":{"tone":"playful","motion_density":"medium"},
         "narration":{"language":"en","voice_character":"narrator"}}
    candidate=ok(client.put(f"/api/v1/channels/{ch['channel_id']}/dna",
        json={"channel_dna":doc,"expected_head_revision":None,"expected_head_artifact_id":None},
        headers={"Idempotency-Key":"dna-"+key}),201)
    ok(client.post(f"/api/v1/channels/{ch['channel_id']}/dna/{candidate['artifact_id']}/approve",
        json={"expected_head_revision":None,"expected_sha256":candidate["sha256"],
              "actor":"qa","reviewed_at":"2026-10-17T00:00:00Z"}))
    return ch

def project(client,ch,key):
    return ok(client.post("/api/v1/projects",json={"channel_id":ch["channel_id"],
          "name":key,"slug":key},headers={"Idempotency-Key":"project-"+key}),201)

def reserved(client,pid,kind,fill):
    prefix=f"/api/v1/projects/{pid}/authoring/{kind}"
    pkg=ok(client.post(prefix+"/prompt",json={}),201)
    doc={**pkg["reserved_fields"],**fill(pkg)}
    report=ok(client.post(prefix+"/validate",json={"reservation_id":pkg["reservation_id"],"document":doc}))
    assert report["valid"],report
    draft=ok(client.post(prefix+"/import",json={"reservation_id":pkg["reservation_id"],"document":doc}),201)
    head=ok(client.get(f"/api/v1/projects/{pid}/workflow"))["stages"][0]["head_revision"]
    ok(client.post(prefix+f"/{draft['artifact_id']}/approve",
        json={"expected_head_revision":head,"expected_sha256":draft["sha256"]}))
    return draft,doc

def build_story(client,pid):
    ideas,idea_doc=reserved(client,pid,"topic-ideas",
        lambda pkg:{"channel_dna_artifact_id":pkg["dna_metadata"]["artifact_id"],
                    "channel_dna_hash":pkg["dna_metadata"]["sha256"],
                    "ideas":[{"idea_id":"idea_one","title":"A story","premise":"A short animated story"}]})
    script,script_doc=reserved(client,pid,"script",
        lambda pkg:{"topic_ideas_artifact_id":ideas["artifact_id"],"selected_idea_id":"idea_one",
                    "full_text":"Hello!","sections":[{"section_id":"section_one","start_char":0,"end_char":6,"text":"Hello!"}]})
    def shot(pkg):
        world={"actors":[{"actor_id":"actor_one","x":0,"y":0,"facing":"right"}],"props":[]}
        return {"script_artifact_id":script["artifact_id"],"script_sha256":script["sha256"],
                "actor_ids":["actor_one"],"prop_ids":[],"location_ids":["location_one"],
                "shots":[{"shot_id":"shot_one","duration_frames":48,"actor_ids":["actor_one"],"prop_ids":[],
                          "location_id":"location_one","utterance":{"text":"Hello!","script_start":0,"script_end":6},
                          "initial_world_state":world,"final_world_state":world,"spatial_anchors":[]}]}
    shotplan,_=reserved(client,pid,"shot-plan",shot)
    return ideas,script,shotplan

def test_real_authoring_and_exact_local_asset_pins(client):
    ch=channel(client,"alpha")
    pa=project(client,ch,"first")
    pid=pa["project_id"]
    build_story(client,pid)
    resolution=ok(client.get(f"/api/v1/projects/{pid}/resolver/resolution"))
    assert resolution["resolved_count"]==0 and resolution["total_count"]>=2
    actor=next(r["requirement"] for r in resolution["requirements"] if r["requirement"]["kind"]=="actor")
    png=io.BytesIO()
    Image.new("RGBA",(64,64),(100,110,120,255)).save(png,format="PNG")
    import_url=f"/api/v1/projects/{pid}/images/import"
    candidate=ok(client.post(import_url,files={"file":("user.png",png.getvalue(),"image/png")},
        data={"kind":actor["kind"],"semantic_key":actor["semantic_key"],"view":actor["view"]}),201)
    url=f"/api/v1/projects/{pid}/assets/{candidate['asset_version_id']}"
    assert client.get(url+"/image").content==png.getvalue()
    ok(client.post(url+"/review",json={"decision":"approved"}))
    pin=ok(client.post(f"/api/v1/projects/{pid}/asset-bindings",json={
        "requirement_id":actor["requirement_id"],"asset_version_id":candidate["asset_version_id"],
        "expected_fingerprint":resolution["requirements_fingerprint"]}))
    again=ok(client.get(f"/api/v1/projects/{pid}/resolver/resolution"))
    assert again["resolved_count"]==1
    assert pin["asset_version_id"]==candidate["asset_version_id"]
    with TestClient(app) as restarted:
        assert restarted.get(url+"/image").content==png.getvalue()
        assert ok(restarted.get(f"/api/v1/projects/{pid}/resolver/resolution"))["resolved_count"]==1
    pb=project(client,ch,"second")
    build_story(client,pb["project_id"])
    rb=ok(client.get(f"/api/v1/projects/{pb['project_id']}/resolver/resolution"))
    actor_b=next(r["requirement"] for r in rb["requirements"] if r["requirement"]["kind"]=="actor")
    ok(client.post(f"/api/v1/projects/{pb['project_id']}/asset-bindings",json={
        "requirement_id":actor_b["requirement_id"],"asset_version_id":candidate["asset_version_id"],
        "expected_fingerprint":rb["requirements_fingerprint"]}))
    other=project(client,channel(client,"beta"),"other")
    build_story(client,other["project_id"])
    rc=ok(client.get(f"/api/v1/projects/{other['project_id']}/resolver/resolution"))
    actor_c=next(r["requirement"] for r in rc["requirements"] if r["requirement"]["kind"]=="actor")
    bad=client.post(f"/api/v1/projects/{other['project_id']}/asset-bindings",json={
        "requirement_id":actor_c["requirement_id"],"asset_version_id":candidate["asset_version_id"],
        "expected_fingerprint":rc["requirements_fingerprint"]})
    assert bad.status_code==404,bad.text

def test_authoring_rejects_corrupt_script_and_bad_image(client):
    ch=channel(client,"alpha")
    pid=project(client,ch,"first")["project_id"]
    reserved(client,pid,"topic-ideas",
        lambda pkg:{"channel_dna_artifact_id":pkg["dna_metadata"]["artifact_id"],
                    "channel_dna_hash":pkg["dna_metadata"]["sha256"],
                    "ideas":[{"idea_id":"idea_one","title":"A story","premise":"A premise"}]})
    pkg=ok(client.post(f"/api/v1/projects/{pid}/authoring/script/prompt",json={}),201)
    ideas=ok(client.get(f"/api/v1/projects/{pid}/authoring/topic-ideas/history"))["items"][0]
    bad={**pkg["reserved_fields"],"topic_ideas_artifact_id":ideas["artifact_id"],"selected_idea_id":"idea_one",
         "full_text":"Hello!","sections":[{"section_id":"sec_one","start_char":0,"end_char":5,"text":"Hello!"}]}
    report=ok(client.post(f"/api/v1/projects/{pid}/authoring/script/validate",
                          json={"reservation_id":pkg["reservation_id"],"document":bad}))
    assert not report["valid"]
    upload=client.post(f"/api/v1/projects/{pid}/images/import",
        files={"file":("fake.png",b"not an image","image/png")},
        data={"kind":"actor","semantic_key":"actor_one","view":"front"})
    assert upload.status_code==422


def test_stale_script_invalidates_shot_and_resolver(client):
    ch=channel(client,"lineage")
    pid=project(client,ch,"story")["project_id"]
    ideas,script,shot=build_story(client,pid)
    reserved(client,pid,"script",lambda pkg:{
       "topic_ideas_artifact_id":ideas["artifact_id"],"selected_idea_id":"idea_one",
       "full_text":"Hello again!","sections":[{"section_id":"section_one","start_char":0,
       "end_char":12,"text":"Hello again!"}]})
    invalid=client.get(f"/api/v1/projects/{pid}/resolver/requirements")
    assert invalid.status_code==409,invalid.text
    assert invalid.json()["error"]["code"]=="STALE_HEAD"
    wf=ok(client.get(f"/api/v1/projects/{pid}/workflow"))
    assert wf["stages"][0]["readiness"]=="stale"
    assert wf["stages"][1]["readiness"]=="blocked"


def test_genuine_optional_analysis_and_immutable_requirements(client):
    ch=channel(client,"analysis")
    pid=project(client,ch,"story")["project_id"]
    ideas,script,shot=build_story(client,pid)
    from app.animation import resolver
    before=resolver.publish_requirements(pid)
    after=resolver.publish_requirements(pid)
    _,analysis=reserved(client,pid,"script-analysis",
       lambda pkg:{"script_artifact_id":script["artifact_id"],
                   "entities":[{"entity_id":"actor_one","kind":"actor","name":"Hero"}],
                   "continuity_notes":["Preserve hero identity"]})
    assert analysis["entities"][0]["entity_id"]=="actor_one"
    assert before["artifact_id"]==after["artifact_id"]
    assert before["sha256"]==after["sha256"]
    with s.reader() as con:
        assert con.execute("SELECT COUNT(*) FROM artifacts WHERE project_id=? AND kind='asset_requirements.v1'",
                           (pid,)).fetchone()[0]==1


def _seed_g(request_client,monkeypatch,tag):
    from app.animation import generation
    monkeypatch.setenv("GLABS_API_KEY","fake-ci-key")
    ch=channel(request_client,tag)
    pid=project(request_client,ch,"story")["project_id"]
    build_story(request_client,pid)
    needed=ok(request_client.get(f"/api/v1/projects/{pid}/resolver/requirements"))
    req=next(x for x in needed["requirements"] if x["kind"]=="actor")
    quote=generation.prepare(pid,req["requirement_id"],"Cartoon hero","",
                             "nano_banana_2","1:1",2.0)
    op=generation.confirm(pid,quote["quote"],quote["fingerprint"],"paid-"+tag,True)
    return pid,req,quote,op


def test_mocked_donor_transport_succeeds_without_live_payment(client,monkeypatch):
    from app.animation import generation
    pid,req,quote,op=_seed_g(client,monkeypatch,"glabs")
    same=generation.confirm(pid,quote["quote"],quote["fingerprint"],"paid-glabs",True)
    assert same["operation_id"]==op["operation_id"]
    with pytest.raises(s.DomainError) as bad:
        generation.confirm(pid,{**quote["quote"],"cost_ceiling_usd":99},quote["fingerprint"],"another",True)
    assert bad.value.code=="CONSENT_INVALID"
    buffer=io.BytesIO()
    Image.new("RGBA",(40,32),(10,20,30,255)).save(buffer,format="PNG")
    class Fake:
        submits=0
        def submit_image(self,payload):
            assert payload["model"]=="nano_banana_2"
            self.submits+=1
            return {"task_id":"abcd1234","status":"pending"}
        def get_status(self,tid):
            assert tid=="abcd1234"
            return {"task_id":tid,"status":"completed"}
        def get_result(self,tid):
            return {"task_id":tid,"status":"completed","results":["http://127.0.0.1:8765/files/a.png"]}
        def download_file(self,url,path,max_bytes):
            assert max_bytes>=len(buffer.getvalue())
            path.write_bytes(buffer.getvalue())
    fake=Fake()
    done=generation.advance(pid,op["operation_id"],client=fake)
    assert done["status"]=="completed",done
    assert fake.submits==1
    assert done["result"]["candidate"]["status"]=="candidate"
    again=generation.advance(pid,op["operation_id"],client=fake)
    assert again["status"]=="completed" and fake.submits==1
    with s.reader() as con:
        assert con.execute("SELECT COUNT(*) FROM operations WHERE project_id=?",(pid,)).fetchone()[0]==1
    with TestClient(app) as restarted:
        persisted=ok(restarted.get(f"/api/v1/projects/{pid}/generation/operations/{op['operation_id']}"))
        assert persisted["status"]=="completed"


def test_ambiguous_submission_never_resubmits(client,monkeypatch):
    from app.animation import generation
    pid,req,quote,op=_seed_g(client,monkeypatch,"unknown")
    class TimedOut:
        calls=0
        def submit_image(self,payload):
            self.calls+=1
            raise TimeoutError("submit ACK lost")
    fake=TimedOut()
    first=generation.advance(pid,op["operation_id"],client=fake)
    assert first["status"]=="unknown"
    second=generation.advance(pid,op["operation_id"],client=fake)
    assert second["status"]=="unknown"
    assert fake.calls==1
    assert generation.cancel(pid,op["operation_id"])["status"]=="cancelled"


def test_cancel_queued_and_orphan_submitted_fence(client,monkeypatch):
    from app.animation import generation
    pid,req,quote,op=_seed_g(client,monkeypatch,"cancel")
    assert generation.cancel(pid,op["operation_id"])["status"]=="cancelled"
    class Never:
        def submit_image(self,payload):raise AssertionError("paid duplicate call")
    assert generation.advance(pid,op["operation_id"],client=Never())["status"]=="cancelled"
    pid2,_,_,op2=_seed_g(client,monkeypatch,"crash")
    with s.writer() as con:
        con.execute("UPDATE operation_tasks SET status='submitted' WHERE operation_id=?",(op2["operation_id"],))
        con.execute("UPDATE operations SET status='running' WHERE operation_id=?",(op2["operation_id"],))
    assert generation.advance(pid2,op2["operation_id"],client=Never())["status"]=="unknown"


def test_image_publish_failure_cleans_only_uncommitted_files(client,monkeypatch):
    from app.animation import local_assets
    ch=channel(client,"orphan")
    pid=project(client,ch,"story")["project_id"]
    png=io.BytesIO()
    Image.new("RGB",(32,32),(10,20,30)).save(png,format="PNG")
    original=s.add_artifact
    def failing(con,**kwargs):
        if kwargs["kind"]=="asset_version.v1":
            raise RuntimeError("injected metadata transaction failure")
        return original(con,**kwargs)
    monkeypatch.setattr(s,"add_artifact",failing)
    with pytest.raises(RuntimeError,match="injected"):
        local_assets.ingest(pid,"actor","actor_one","front",png.getvalue(),"test.png")
    with s.reader() as con:
        assert con.execute("SELECT COUNT(*) FROM asset_versions").fetchone()[0]==0
        assert con.execute("SELECT COUNT(*) FROM assets").fetchone()[0]==0
        assert con.execute("SELECT COUNT(*) FROM artifacts WHERE kind='asset_source_image.v1'").fetchone()[0]==0
    image_root=s.artifact_root()/"channels"/ch["channel_id"]
    assert list(image_root.glob("images/**/*.*"))==[]
    assert list(image_root.glob("asset_versions/*.json"))==[]


def test_newer_asset_version_does_not_replace_existing_pin(client):
    ch=channel(client,"pins")
    pid=project(client,ch,"story")["project_id"]
    build_story(client,pid)
    current=ok(client.get(f"/api/v1/projects/{pid}/resolver/resolution"))
    actor=next(x["requirement"] for x in current["requirements"] if x["requirement"]["kind"]=="actor")
    pic=io.BytesIO()
    Image.new("RGB",(32,32),(10,20,30)).save(pic,format="PNG")
    versions=[]
    for index in range(2):
        candidate=ok(client.post(f"/api/v1/projects/{pid}/images/import",
            files={"file":("test.png",pic.getvalue(),"image/png")},
            data={"kind":"actor","semantic_key":"actor_one","view":"front"}),201)
        ok(client.post(f"/api/v1/projects/{pid}/assets/{candidate['asset_version_id']}/review",
                       json={"decision":"approved"}))
        versions.append(candidate["asset_version_id"])
    assert versions[0]!=versions[1]
    ok(client.post(f"/api/v1/projects/{pid}/asset-bindings",
        json={"requirement_id":actor["requirement_id"],"asset_version_id":versions[0],
              "expected_fingerprint":current["requirements_fingerprint"]}))
    persisted=ok(client.get(f"/api/v1/projects/{pid}/resolver/resolution"))
    selected=next(x for x in persisted["requirements"] if x["requirement"]["kind"]=="actor")
    assert selected["binding"]["asset_version_id"]==versions[0]
    rejected=client.post(f"/api/v1/projects/{pid}/asset-bindings",
        json={"requirement_id":actor["requirement_id"],"asset_version_id":versions[1],
              "expected_fingerprint":current["requirements_fingerprint"]})
    assert rejected.status_code==409


def test_resolver_unknown_rig_capability_is_not_approved(client):
    from app.animation.resolver import compatible
    ch=channel(client,"capability")
    pid=project(client,ch,"story")["project_id"]
    build_story(client,pid)
    state=ok(client.get(f"/api/v1/projects/{pid}/resolver/resolution"))
    assert state["rig_capability_status"]=="pending_c4_rig_validation"
    actor=next(x["requirement"] for x in state["requirements"] if x["requirement"]["kind"]=="actor")
    version={"status":"approved","kind":"actor","semantic_key":"actor_one","view_key":"front",
             "visual_style_hash":"a"*64,"capability_hash":s.sha([])}
    assert compatible(actor,version,"a"*64)
    assert not compatible({**actor,"required_capabilities":["grab"]},version,"a"*64)
    assert not compatible(actor,{**version,"view_key":"left"},"a"*64)
    assert not compatible(actor,version,"b"*64)


def test_unknown_submission_reconcile_known_handle_only(client,monkeypatch):
    from app.animation import generation
    pid,req,quote,op=_seed_g(client,monkeypatch,"reconcile")
    class LostAck:
        calls=0
        def submit_image(self,body):
            self.calls+=1
            raise TimeoutError("real paid request may have been submitted")
    missing=LostAck()
    assert generation.advance(pid,op["operation_id"],client=missing)["status"]=="unknown"
    with pytest.raises(s.DomainError) as e:
        generation.reconcile_unknown(pid,op["operation_id"],"12345678",False)
    assert e.value.code=="CONSENT_INVALID"
    class KnownTask:
        calls=0
        def submit_image(self,body):
            self.calls+=1
            raise AssertionError("No second paid POST allowed")
        def get_status(self,task_id):
            assert task_id=="1234abcd"
            return {"task_id":task_id,"status":"pending"}
    matched=KnownTask()
    result=generation.reconcile_unknown(pid,op["operation_id"],"1234abcd",True,client=matched)
    assert result["status"]=="running"
    assert matched.calls==0 and missing.calls==1
    assert result["task"]["provider_handle_json"] is not None


def test_glabs_invalid_reconcile_task_id_returns_typed_error(client,monkeypatch):
    from app.animation import generation
    pid,req,quote,op=_seed_g(client,monkeypatch,"badhandle")
    class Lost:
        def submit_image(self,payload):
            raise TimeoutError("ambiguous ACK")
    assert generation.advance(pid,op["operation_id"],client=Lost())["status"]=="unknown"
    response=client.post(f"/api/v1/projects/{pid}/generation/operations/{op['operation_id']}/reconcile",
        json={"provider_task_id":"INVALID_TASK_ID","confirmed_owner_match":True})
    assert response.status_code==502,response.text
    assert response.json()["error"]["code"]=="MEDIA_PROVIDER_UPSTREAM_ERROR"
