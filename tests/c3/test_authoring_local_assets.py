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
