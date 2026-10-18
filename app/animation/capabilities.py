"""C5 additive, immutable motion-capability evidence; NEVER rewrite approved C4 profile."""
from __future__ import annotations
import base64
import io
import json
import math
from pathlib import Path
from PIL import Image,UnidentifiedImageError

from app.animation import service as s, authoring as a, rig_resolution, rig_proof, rig_pixels as px

KIND="rig_motion_capabilities.v1"
ACTIONS=("idle","walk_to","look_at","reach_for","grab","carry_to","place_at","point_at","react")
REQUIRED=("root","hip","chest","head","left_upper_arm","left_lower_arm","left_hand",
 "right_upper_arm","right_lower_arm","right_hand","left_upper_leg","left_lower_leg","left_foot",
 "right_upper_leg","right_lower_leg","right_foot")

def _selected(con,pid,rig_version_id):
    pr=a.project(con,pid)
    if rig_resolution.status(con,pid)[0]!="approved":
        s.error("UNAPPROVED_DEPENDENCY","Approve all C4 actor rigs first",422)
    doc=rig_resolution._document(rig_resolution._latest(con,pid,pr["channel_id"]))
    matches=[x for x in doc["bindings"] if x["rig_version_id"]==rig_version_id]
    if not matches:s.error("NOT_FOUND","Rig not selected by current project",404)
    rv=con.execute("SELECT * FROM rig_versions WHERE rig_version_id=? AND channel_id=? AND status='approved'",
                   (rig_version_id,pr["channel_id"])).fetchone()
    if rv is None:s.error("NOT_FOUND","Approved rig version missing",404)
    _,meta,docs=rig_proof._candidate_readonly(con,pr["channel_id"],rv["rig_id"],rig_version_id)
    manifest=con.execute("SELECT * FROM artifacts WHERE artifact_id=?",(rv["rig_manifest_artifact_id"],)).fetchone()
    rig_proof.recorded(con,pr["channel_id"],rv["rig_id"],rig_version_id,
                       con.execute("SELECT project_id FROM artifacts WHERE artifact_id=?",
                                   (rv["rig_manifest_artifact_id"],)).fetchone()[0])
    skeleton=json.loads(s.bounded_path(meta["base"]+"/skeleton.json").read_bytes())
    return pr,rv,docs,manifest,skeleton

def _source(manifest,rig):
    return s.sha({"rig_version_id":rig["rig_version_id"],
                  "rig_manifest_id":manifest["artifact_id"],"rig_manifest_sha":manifest["sha256"],
                  "engine":"c5-motion.v1","actions":ACTIONS})

def _existing(con,cid,version,source):
    return con.execute("""SELECT * FROM artifacts WHERE channel_id=? AND kind=? AND logical_key=?
       AND approval_status='approved' AND json_extract(metadata_json,'$.source_fingerprint')=?
       ORDER BY revision DESC LIMIT 1""",(cid,KIND,version,source)).fetchone()

def certified(con,channel_id,rig_version_id,manifest_id,manifest_sha):
    key=s.sha({"rig_version_id":rig_version_id,
               "rig_manifest_id":manifest_id,"rig_manifest_sha":manifest_sha,
               "engine":"c5-motion.v1","actions":ACTIONS})
    record=_existing(con,channel_id,rig_version_id,key)
    if record is None:return None
    doc=a.verified_doc(record)
    if (doc.get("rig_version_id")!=rig_version_id or
        doc.get("rig_manifest_artifact_id")!=manifest_id or
        doc.get("rig_manifest_sha256")!=manifest_sha or tuple(doc.get("actions",[]))!=ACTIONS):
        s.error("LINEAGE_MISMATCH","Motion capability certification metadata mismatch",422)
    return record

def proof(pid,version_id,samples):
    with s.reader() as con:
        pr,rv,docs,manifest,sk=_selected(con,pid,version_id)
        key=_source(manifest,rv)
        existing=_existing(con,pr["channel_id"],version_id,key)
        if existing is not None:return s.artifact_view(existing)
        required=set(REQUIRED)
        actual={x["name"] for x in sk["bones"]}
        if not required.issubset(actual):
            s.error("RIG_CAPABILITY_UNSUPPORTED","Rig misses mandatory motion bones",422)
        bones={x["name"]:x for x in sk["bones"]}
        for side in ("left","right"):
            for end in ("lower_arm","hand","lower_leg","foot"):
                child=bones[f"{side}_{end}"]
                if math.hypot(child.get("x",0),child.get("y",0))<2:
                    s.error("RIG_CAPABILITY_UNSUPPORTED","Rig has collapsed limb joint: "+side+" "+end,422)
        channel=pr["channel_id"]
        manifest_id=manifest["artifact_id"];manifest_sha=manifest["sha256"]
    if not isinstance(samples,list) or len(samples)!=9 or tuple(x.get("action") for x in samples)!=ACTIONS:
        s.error("VALIDATION_FAILED","Nine ordered real runtime action poses required",422)
    signatures=[];bone_samples={}
    for action,sample in zip(ACTIONS,samples):
        rotations=sample.get("bones")
        if not isinstance(rotations,dict) or not required.issubset(rotations):
            s.error("RIG_CAPABILITY_UNSUPPORTED","Runtime bone inventory incomplete: "+action,422)
        if any(type(x) not in (float,int) or not math.isfinite(x) for x in rotations.values()):
            s.error("VALIDATION_FAILED","Nonfinite real runtime rotation",422)
        if sample.get("bone_count",0)<16 or sample.get("attached_slot_count",0)<14:
            s.error("RIG_CAPABILITY_UNSUPPORTED","Spine runtime attachments missing",422)
        root=sample.get("root")
        if not isinstance(root,dict) or any(type(root.get(k)) not in (float,int) for k in ("x","y")):
            s.error("VALIDATION_FAILED","Runtime root missing",422)
        raw=sample.get("png_base64","")
        if type(raw)!=str or len(raw)>200000:
            s.error("VALIDATION_FAILED","Oversized runtime image",422)
        try:
            png=base64.b64decode(raw,validate=True)
            with Image.open(io.BytesIO(png)) as image:
                image.load()
                if image.format!="PNG" or image.width<150 or image.height<150 or image.width>1024 or image.height>1024:
                    s.error("VALIDATION_FAILED","Runtime capture format/dimensions invalid",422)
                low_variance=image.convert("RGB").getcolors(maxcolors=2)
                if low_variance is not None:
                    s.error("VALIDATION_FAILED","Blank Spine runtime frame",422)
        except (OSError,UnidentifiedImageError,ValueError) as exc:
            s.error("VALIDATION_FAILED","Invalid real runtime screenshot: "+str(exc),422)
        signatures.append(s.sha({"png":px.digest(png),"bones":rotations,"root":root}))
        bone_samples[action]=rotations
    if len(set(signatures))!=len(ACTIONS):
        s.error("RIG_CAPABILITY_UNSUPPORTED","Nine action poses must be visually distinct",422)
    start=bone_samples["idle"]
    changes={"walk_to":["left_upper_leg","right_upper_leg"],
             "look_at":["head"],"reach_for":["left_upper_arm","left_lower_arm"],
             "grab":["left_hand"],"carry_to":["left_upper_leg","right_upper_leg"],
             "place_at":["left_lower_arm"],"point_at":["right_upper_arm"],
             "react":["chest","head"]}
    for action,targets in changes.items():
        if not any(abs(bone_samples[action][name]-start[name])>2 for name in targets):
            s.error("RIG_CAPABILITY_UNSUPPORTED","Runtime pose does not articulate required bones: "+action,422)
    for action in ("walk_to","carry_to"):
        if abs(samples[ACTIONS.index(action)]["root"]["x"]-samples[0]["root"]["x"])<15:
            s.error("RIG_CAPABILITY_UNSUPPORTED","Locomotion proof has no root translation",422)
    doc={"schema_version":KIND,"artifact_id":s.uid("ar"),"channel_id":channel,
         "project_id":pid,"rig_version_id":version_id,"rig_manifest_artifact_id":manifest_id,
         "rig_manifest_sha256":manifest_sha,"source_fingerprint":key,
         "actions":list(ACTIONS),"runtime_package":"@esotericsoftware/spine-pixi-v8",
         "runtime_version":"4.2.120","created_at":s.now(),
         "captures_sha256":signatures}
    aid=doc["artifact_id"]
    rel=f"rigs/motion-certifications/{version_id}/{aid}.json"
    def commit(con,digest,size):
        pr,rv,docs,manifest2,_=_selected(con,pid,version_id)
        if _source(manifest2,rv)!=key:s.error("STALE_HEAD","Rig identity changed while certifying")
        prior=_existing(con,channel,version_id,key)
        if prior:return s.artifact_view(prior)
        revision=con.execute("SELECT COALESCE(MAX(revision),0)+1 FROM artifacts WHERE channel_id=? AND kind=? AND logical_key=?",
                             (channel,KIND,version_id)).fetchone()[0]
        s.add_artifact(con,aid=aid,channel_id=channel,project_id=pid,kind=KIND,schema=KIND,
               logical=version_id,revision=revision,status="approved",
               checksum=digest,size=size,relative=rel,
               metadata={"source_fingerprint":key,"rig_manifest_sha256":manifest_sha,
                         "runtime_version":"4.2.120"})
        return s.artifact_view(con.execute("SELECT * FROM artifacts WHERE artifact_id=?",(aid,)).fetchone())
    return s.document_publish(doc,rel,commit)


def list_for_project(pid):
    with s.reader() as con:
        pr=a.project(con,pid)
        readiness,blockers=rig_resolution.status(con,pid)
        if readiness!="approved":
            return {"readiness":"blocked","blockers":blockers,"rigs":[]}
        selected=rig_resolution._document(rig_resolution._latest(con,pid,pr["channel_id"]))
        items=[]
        seen=set()
        for item in selected["bindings"]:
            version=item["rig_version_id"]
            if version in seen:continue
            seen.add(version)
            project,rv,docs,manifest,skeleton=_selected(con,pid,version)
            cert=certified(con,pr["channel_id"],version,manifest["artifact_id"],manifest["sha256"])
            items.append({"rig_version_id":version,"rig_id":rv["rig_id"],
              "rig_manifest_artifact_id":manifest["artifact_id"],
              "rig_manifest_sha256":manifest["sha256"],
              "certified":cert is not None,"certification_artifact_id":cert["artifact_id"] if cert else None,
              "capabilities":list(ACTIONS) if cert else docs["profile"]["capabilities"]})
        return {"readiness":"approved","blockers":[],"rigs":items}
