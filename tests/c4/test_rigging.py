"""C4 pixel, draft revision and rig candidate integration on real SQLite/Pillow."""
import io
import json
import pytest
from PIL import Image, ImageDraw
from fastapi.testclient import TestClient

from app.main import app
from app.animation import rig_pixels as px
from app.animation import service as s

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv("DATABASE_URL","sqlite:///"+(tmp_path/"animation.db").as_posix())
    monkeypatch.setenv("ARTIFACT_ROOT",str(tmp_path/"artifacts"))
    monkeypatch.setenv("AUTO_APPLY_MIGRATIONS","true")
    with TestClient(app) as http:
        yield http

def ok(response,code=200):
    assert response.status_code==code,response.text
    return response.json()["data"]

def setup(client,slug):
    ch=ok(client.post("/api/v1/channels",json={"name":slug,"slug":slug},
        headers={"Idempotency-Key":slug}),201)
    doc={"schema_version":"channel_dna.v2",
         "identity":{"name":"Animation","audience":"Viewers"},
         "visual":{"style":"Drawn 2D characters","palette":["#aabbcc"]},
         "performance":{"tone":"playful","motion_density":"medium"},
         "narration":{"language":"en","voice_character":"narrator"}}
    rev=ok(client.put(f"/api/v1/channels/{ch['channel_id']}/dna",
        json={"channel_dna":doc,"expected_head_revision":None,"expected_head_artifact_id":None},
        headers={"Idempotency-Key":"dna-"+slug}),201)
    ok(client.post(f"/api/v1/channels/{ch['channel_id']}/dna/{rev['artifact_id']}/approve",
        json={"expected_head_revision":None,"expected_sha256":rev["sha256"],
              "actor":"test","reviewed_at":"2026-10-18T00:00:00Z"}))
    pr=ok(client.post("/api/v1/projects",json={"channel_id":ch["channel_id"],
            "name":slug,"slug":slug},headers={"Idempotency-Key":"project-"+slug}),201)
    return ch["channel_id"],pr["project_id"]

def drawing(which):
    """Two independently constructed actual raster cartoon silhouettes."""
    image=Image.new("RGBA",(320,400),(0,0,0,0))
    dr=ImageDraw.Draw(image)
    if which=="a":
        dr.ellipse((105,28,214,112),fill="#efb378")
        dr.polygon([(90,115),(220,115),(235,230),(80,230)],fill="#2d7dc4")
        dr.polygon([(95,218),(218,218),(211,258),(104,258)],fill="#b98036")
        dr.polygon([(83,120),(44,134),(18,268),(38,284),(65,175)],fill="#efb378")
        dr.polygon([(230,116),(262,138),(305,272),(288,284),(249,178)],fill="#efb378")
        dr.polygon([(111,251),(154,251),(149,352),(141,387),(106,389)],fill="#527b53")
        dr.polygon([(170,250),(215,250),(214,350),(241,385),(202,389)],fill="#527b53")
        dr.arc((113,40,204,92),0,175,fill="#563b2e",width=6)
    else:
        dr.polygon([(143,10),(160,39),(196,16),(218,75),(106,80)],fill="#7f4bda")
        dr.ellipse((110,39,215,140),fill="#b9895d")
        dr.polygon([(75,135),(239,139),(219,252),(90,245)],fill="#d74957")
        dr.polygon([(80,244),(240,244),(215,276),(102,278)],fill="#472d91")
        dr.polygon([(77,145),(45,161),(21,249),(49,272),(82,185)],fill="#b9895d")
        dr.polygon([(240,146),(276,162),(301,250),(277,276),(244,185)],fill="#b9895d")
        dr.polygon([(103,269),(150,269),(154,360),(130,389),(87,382)],fill="#dfbd77")
        dr.polygon([(174,267),(216,267),(223,355),(255,377),(218,390)],fill="#dfbd77")
    buffer=io.BytesIO()
    image.save(buffer,format="PNG")
    return buffer.getvalue()

def upload(client,pid,which):
    response=client.post(f"/api/v1/projects/{pid}/images/import",
       data={"kind":"actor","semantic_key":"actor_"+which,"view":"front"},
       files={"file":("illustration-"+which+".png",drawing(which),"image/png")})
    version=ok(response,201)["asset_version_id"]
    ok(client.post(f"/api/v1/projects/{pid}/assets/{version}/review",json={"decision":"approved"}))
    return version

def test_real_pixel_extract_and_two_distinct_drafts(client):
    _,pid=setup(client,"pixela")
    a=upload(client,pid,"a")
    b=upload(client,pid,"b")
    assert a!=b
    base=f"/api/v1/projects/{pid}/rigging/rigs"
    da=ok(client.post(base,json={"asset_version_id":a}),201)
    db=ok(client.post(base,json={"asset_version_id":b}),201)
    assert da["rig_id"]!=db["rig_id"]
    for d in (da,db):
        url=base+"/"+d["rig_id"]
        doc=ok(client.get(url))
        assert set(doc["parts"])==set(px.ROLES)
        assert all(not p["reviewed"] for p in doc["parts"].values())
        assert len(doc["parts"])==14
        mask=client.get(url+"/parts/head/mask")
        assert mask.status_code==200
        with Image.open(io.BytesIO(mask.content)) as actual:
            assert actual.mode=="L" and actual.size==(320,400)
        blocked=client.post(url+"/export",json={"expected_revision":1})
        assert blocked.status_code==422
    with TestClient(app) as restarted:
        assert ok(restarted.get(base+"/"+da["rig_id"]))["source_version"]==a

def test_manual_brush_revision_and_source_rejection(client):
    cid,pid=setup(client,"brusha")
    version=upload(client,pid,"a")
    base=f"/api/v1/projects/{pid}/rigging/rigs"
    draft=ok(client.post(base,json={"asset_version_id":version}),201)
    url=base+"/"+draft["rig_id"]
    first=client.get(url+"/parts/head/mask").content
    edit=ok(client.post(url+"/parts/head",json={
        "expected_revision":1,
        "strokes":[{"x":.5,"y":.5,"radius":.03,"mode":"paint"}],
        "pivot":{"x":.51,"y":.27},"layer":9}))
    assert edit["draft_revision"]==2
    assert client.get(url+"/parts/head/mask").content!=first
    assert ok(client.get(url))["parts"]["head"]["pivot"]["x"]==.51
    assert client.post(url+"/parts/head",json={"expected_revision":1,"reviewed":True}).status_code==409
    other_cid,other_pid=setup(client,"brushb")
    bad=client.post(f"/api/v1/projects/{other_pid}/rigging/rigs",json={"asset_version_id":version})
    assert bad.status_code==422
    assert other_cid!=cid

def test_fourteen_real_reviewed_sprites_export_and_approval_block(client):
    cid,pid=setup(client,"exporta")
    version=upload(client,pid,"b")
    base=f"/api/v1/projects/{pid}/rigging/rigs"
    draft=ok(client.post(base,json={"asset_version_id":version}),201)
    url=base+"/"+draft["rig_id"]
    revision=1
    # Explicit human-review simulation; blank auto regions repaired with real
    # transparent replacement rather than silently credited to extraction.
    repair=Image.new("RGBA",(50,50),(0,0,0,0))
    ImageDraw.Draw(repair).ellipse((8,8,41,41),fill="#b9895d")
    out=io.BytesIO();repair.save(out,format="PNG")
    for role in px.ROLES:
        sprite=client.get(url+"/parts/"+role+"/sprite")
        assert sprite.status_code==200
        with Image.open(io.BytesIO(sprite.content)) as img:
            blank=img.getchannel("A").getbbox() is None
        if blank:
            revision=ok(client.post(url+"/parts/"+role+"/replacement",
                       files={"file":(role+".png",out.getvalue(),"image/png")},
                       data={"expected_revision":str(revision)}))["draft_revision"]
        revision=ok(client.post(url+"/parts/"+role,
                     json={"expected_revision":revision,"reviewed":True}))["draft_revision"]
    exported=ok(client.post(url+"/export",json={"expected_revision":revision}),201)
    assert exported["candidate"] is True
    rid=exported["rig_version_id"]
    files=f"/api/v1/channels/{cid}/rigs/{draft['rig_id']}/versions/{rid}/"
    skeleton=json.loads(client.get(files+"skeleton.json").content)
    assert {b["name"] for b in skeleton["bones"]}==set(px.BONES)
    assert set(skeleton["skins"][0]["attachments"])==set(px.ROLES)
    atlas=client.get(files+"skeleton.atlas").text
    assert all("\n"+role+"\n" in atlas for role in px.ROLES)
    assert client.get(files+"page.png").status_code==200
    assert client.post(f"/api/v1/channels/{cid}/rigs/{draft['rig_id']}/approve",
          json={"rig_version_id":rid,"expected_revision":exported["revision"]}).status_code==409
    assert ok(client.get(base))["items"][0]["status"]=="candidate"
