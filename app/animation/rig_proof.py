"""C4 official-runtime evidence ingestion for a single-user local rigging workshop.

The browser evaluates the actual official spine-pixi loader and exports five PNG
poses with the runtime's live bone values; this API independently checks file
lineage, real raster evidence, pose deltas and attachment inventory. It is NOT
cryptographic remote attestation or a commercial Spine-license credential.
"""
from __future__ import annotations

import base64
import binascii
import io
import json
import math
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from app.animation import service as s
from app.animation import rig_pixels as px
from app.animation import rigging as r

POSES = ("idle", "walk", "reach", "grab", "neutral_return")
MAX_PNG_BYTES = 330_000


def _candidate(con, channel_id, rig_id, version_id, *, allow_approved=False):
    row=con.execute("""
        SELECT rv.*,a.project_id,a.metadata_json
        FROM rig_versions rv
        JOIN artifacts a ON a.artifact_id=rv.rig_manifest_artifact_id
        WHERE rv.channel_id=? AND rv.rig_id=? AND rv.rig_version_id=?
    """,(channel_id,rig_id,version_id)).fetchone()
    if row is None:
        s.error("NOT_FOUND","Rig candidate not found",404)
    if row["status"] != "candidate" and not (allow_approved and row["status"]=="approved"):
        s.error("STALE_HEAD","Rig version has already been reviewed")
    if not row["project_id"]:
        s.error("LINEAGE_MISMATCH","Rig manifest must be owned by a project",422)
    metadata=json.loads(row["metadata_json"])
    base=metadata["base"]
    documents={}
    for name in ("parts","profile","manifest"):
        kind={"parts":"parts_manifest.v1","profile":"rig_profile.v1",
              "manifest":"rig_manifest.v1"}[name]
        expected_path=base+"/"+name+".json"
        path=s.bounded_path(expected_path)
        expected_id=(row["rig_manifest_artifact_id"] if name=="manifest"
                     else row["rig_profile_artifact_id"] if name=="profile" else None)
        if not path.is_file():
            s.error("LINEAGE_MISMATCH","Rig version metadata missing",422)
        raw=path.read_bytes()
        try:
            doc=json.loads(raw)
        except (ValueError,UnicodeError):
            s.error("LINEAGE_MISMATCH","Corrupt immutable rig metadata",422)
        if expected_id is None:
            expected_id=doc.get("artifact_id")
        ar=con.execute("SELECT * FROM artifacts WHERE artifact_id=? AND channel_id=? AND project_id=?",
                       (expected_id,channel_id,row["project_id"])).fetchone()
        if (ar is None or ar["kind"]!=kind or ar["schema_version"]!=kind
            or ar["relative_path"]!=expected_path
            or ar["sha256"]!=px.digest(raw) or ar["byte_size"]!=len(raw)
            or doc.get("artifact_id")!=expected_id
            or doc.get("channel_id")!=channel_id):
            s.error("LINEAGE_MISMATCH",kind+" immutable artifact hash/ownership mismatch",422)
        r._validate(kind,doc)
        documents[name]=doc
    if documents["manifest"]["rig_version_id"]!=version_id:
        s.error("LINEAGE_MISMATCH","Rig manifest version differs",422)
    if documents["profile"]["parts_manifest_artifact_id"]!=documents["parts"]["artifact_id"]:
        s.error("LINEAGE_MISMATCH","Profile references the wrong parts",422)
    if documents["manifest"]["rig_profile_artifact_id"]!=documents["profile"]["artifact_id"] or documents["manifest"]["parts_manifest_artifact_id"]!=documents["parts"]["artifact_id"]:
        s.error("LINEAGE_MISMATCH","Rig manifest parent references differ",422)
    if set(x["role"] for x in documents["parts"]["parts"])!=set(px.ROLES):
        s.error("RIG_REQUIRED_PART_MISSING","Export lacks mandatory parts",422)
    if len(documents["profile"]["bones"])!=len({item["role"] for item in documents["profile"]["bones"]}):
        s.error("RIG_REQUIRED_BONE_MISSING","Duplicate semantic bone roles",422)
    if not set(px.BONES).issubset({item["role"] for item in documents["profile"]["bones"]}):
        s.error("RIG_REQUIRED_BONE_MISSING","Export misses mandatory bone roles",422)
    if set(documents["profile"]["capabilities"])!={"idle","walk_to","reach_for","grab"}:
        s.error("RIG_CAPABILITY_INVALID","Verified C4 pose set differs",422)
    pr,asset,path = r._source(con,row["project_id"],documents["parts"]["asset_version_id"])
    if asset["source_sha256"] != documents["parts"]["source_image_sha256"]:
        s.error("RIG_SOURCE_STALE","Original source image SHA differs",409)
    if metadata.get("style_hash")!=asset["visual_style_hash"]:
        s.error("RIG_SOURCE_STALE","Rig was exported under another visual style",409)
    for filename,key in (("skeleton.json","skeleton_sha256"),("skeleton.atlas","atlas_sha256")):
        p=s.bounded_path(base+"/"+filename)
        if not p.is_file() or s.filehash(p)[0]!=documents["manifest"][key]:
            s.error("LINEAGE_MISMATCH",filename+" no longer matches manifest digest",422)
    sk=json.loads(s.bounded_path(base+"/skeleton.json").read_bytes())
    if not sk.get("skeleton",{}).get("spine","").startswith("4.2."):
        s.error("SPINE_VERSION_MISMATCH","Incompatible skeleton format",422)
    names={b["name"] for b in sk.get("bones",[])}
    if not set(px.BONES).issubset(names):
        s.error("RIG_REQUIRED_BONE_MISSING","Skeleton lacks actual mandatory bones",422)
    if {slot["name"] for slot in sk.get("slots",[])} != set(px.ROLES):
        s.error("RIG_ATTACHMENT_MISSING","Runtime slot inventory mismatch",422)
    atlas=s.bounded_path(base+"/skeleton.atlas").read_text()
    if atlas.splitlines()[0]!="page.png":
        s.error("RIG_ATLAS_INVALID","Atlas texture page identity mismatch",422)
    for role in px.ROLES:
        if "\n"+role+"\n" not in "\n"+atlas:
            s.error("RIG_ATLAS_INVALID",role+" atlas region missing",422)
    for item in documents["parts"]["parts"]:
        role=item["role"]
        for suffix,key in ((".png","png_sha256"),(".mask.png","mask_sha256")):
            p=s.bounded_path(base+"/"+role+suffix)
            if not p.is_file() or s.filehash(p)[0]!=item[key]:
                s.error("LINEAGE_MISMATCH",role+" verified texture/mask digest mismatch",422)
        with Image.open(s.bounded_path(base+"/"+role+".png")) as image:
            image.load()
            if image.mode!="RGBA" or image.getchannel("A").getbbox() is None:
                s.error("RIG_REQUIRED_PART_EMPTY",role+" sprite invalid",422)
        entry=con.execute("SELECT * FROM artifacts WHERE artifact_id=? AND project_id=?",
                          (item["sprite_artifact_id"],row["project_id"])).fetchone()
        if entry is None or entry["sha256"]!=item["png_sha256"]:
            s.error("LINEAGE_MISMATCH",role+" sprite artifact identity differs",422)
    page=s.bounded_path(base+"/page.png")
    if not page.is_file():
        s.error("RIG_ATLAS_INVALID","Texture atlas page missing",422)
    with Image.open(page) as image:
        image.load()
        if image.mode!="RGBA" or image.getchannel("A").getbbox() is None:
            s.error("RIG_ATLAS_INVALID","Atlas page is blank",422)
    return row,metadata,documents


def _png_sample(sample):
    raw_string=sample.get("png_base64")
    if not isinstance(raw_string,str) or len(raw_string)>MAX_PNG_BYTES*4//3+32:
        s.error("RIG_LOADER_EVIDENCE_INVALID","Invalid or excessive PNG proof size",422)
    try:
        raw=base64.b64decode(raw_string,validate=True)
    except (binascii.Error,ValueError):
        s.error("RIG_LOADER_EVIDENCE_INVALID","Corrupt base64 screenshot",422)
    if len(raw)>MAX_PNG_BYTES or not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        s.error("RIG_LOADER_EVIDENCE_INVALID","Pose screenshot must be bounded real PNG",422)
    try:
        with Image.open(io.BytesIO(raw)) as im:
            im.verify()
        with Image.open(io.BytesIO(raw)) as im:
            im.load()
            if im.size!=(720,540):
                s.error("RIG_LOADER_EVIDENCE_INVALID","Pose viewport dimensions changed",422)
            image=im.convert("RGB")
            bg=image.getpixel((0,0))
            differences=0
            colors=set()
            for y in range(10,540,7):
                for x in range(10,720,7):
                    color=image.getpixel((x,y))
                    colors.add(color)
                    if sum(abs(a-b) for a,b in zip(bg,color))>45:
                        differences+=1
            if differences<80 or len(colors)<3:
                s.error("RIG_LOADER_EVIDENCE_INVALID","Pose capture has insufficient visible character pixels",422)
    except (OSError,UnidentifiedImageError,ValueError) as exc:
        s.error("RIG_LOADER_EVIDENCE_INVALID","Unreadable pose raster: "+str(exc),422)
    return px.digest(raw)


def _check_poses(poses,sk):
    if not isinstance(poses,list) or len(poses)!=len(POSES):
        s.error("RIG_LOADER_EVIDENCE_INVALID","Five pose captures are required",422)
    if tuple(item.get("pose") for item in poses)!=POSES:
        s.error("RIG_LOADER_EVIDENCE_INVALID","Pose sequence must be idle/walk/reach/grab/neutral_return",422)
    required=set(px.BONES)
    baseline={bone["name"]:float(bone.get("rotation",0)) for bone in sk["bones"]}
    images=[]
    for sample in poses:
        poses_map=sample.get("bones")
        if not isinstance(poses_map,dict) or set(poses_map)!=required:
            s.error("RIG_LOADER_EVIDENCE_INVALID","Runtime bone inventory is incomplete",422)
        expected=px.PRESETS[sample["pose"]]
        for bone in required:
            angle=poses_map[bone]
            if type(angle) not in (int,float) or not math.isfinite(angle):
                s.error("RIG_LOADER_EVIDENCE_INVALID","Non-finite runtime bone rotation",422)
            if abs(angle-(baseline.get(bone,0)+expected.get(bone,0)))>.2:
                s.error("RIG_LOADER_EVIDENCE_INVALID","Live runtime pose differs: "+sample["pose"]+" / "+bone,422)
        if sample.get("bone_count",0)<16 or sample.get("slot_count",0)<14 or sample.get("attached_slot_count",0)<14:
            s.error("RIG_LOADER_EVIDENCE_INVALID","Skeleton slot/bone attachments missing",422)
        images.append(_png_sample(sample))
    if len(set(images[:4]))!=4:
        s.error("RIG_LOADER_EVIDENCE_INVALID","Four articulated poses are not visibly distinct",422)
    if images[0]!=images[-1]:
        s.error("RIG_LOADER_EVIDENCE_INVALID","Neutral reset did not reproduce setup image",422)
    return images


def verify(channel_id,rig_id,version_id,payload):
    if set(payload)!={"source_sha256","skeleton_sha256","atlas_sha256","poses","runtime_package","runtime_version","pixi_version"}:
        s.error("RIG_LOADER_EVIDENCE_INVALID","Unsupported runtime proof payload fields",422)
    with s.reader() as con:
        row,metadata,documents=_candidate(con,channel_id,rig_id,version_id)
        manifest=documents["manifest"]
        for key in ("skeleton_sha256","atlas_sha256"):
            if payload[key]!=manifest[key]:
                s.error("LINEAGE_MISMATCH","Runtime proof does not match frozen export",422)
        if payload["source_sha256"]!=documents["parts"]["source_image_sha256"]:
            s.error("LINEAGE_MISMATCH","Runtime proof refers to wrong source version",422)
        if any(payload[key]!=manifest[key] for key in ("runtime_package","runtime_version","pixi_version")):
            s.error("SPINE_VERSION_MISMATCH","Proof reported wrong official runtime identity",422)
        sk=json.loads(s.bounded_path(metadata["base"]+"/skeleton.json").read_bytes())
        images=_check_poses(payload["poses"],sk)
        prior=con.execute("""
            SELECT * FROM artifacts WHERE project_id=? AND channel_id=?
              AND kind='rig_runtime_proof.v1' AND logical_key=?
        """,(row["project_id"],channel_id,version_id)).fetchone()
        if prior:
            s.error("RIG_PROOF_ALREADY_RECORDED","Runtime evidence already immutable for this candidate",409)
        pid=row["project_id"]
    aid=s.uid("ar")
    doc={
        "schema_version":"rig_runtime_proof.v1",
        "artifact_id":aid,
        "channel_id":channel_id,
        "rig_id":rig_id,
        "rig_version_id":version_id,
        "source_image_sha256":payload["source_sha256"],
        "skeleton_sha256":payload["skeleton_sha256"],
        "atlas_sha256":payload["atlas_sha256"],
        "runtime_package":payload["runtime_package"],
        "runtime_version":payload["runtime_version"],
        "pixi_version":payload["pixi_version"],
        "pose_png_sha256":dict(zip(POSES,images)),
        "poses":payload["poses"],
        "created_at":s.now()
    }
    path=f"rigs/{rig_id}/versions/{version_id}/proof/{aid}.json"
    def commit(con,checksum,size):
        fresh,meta,docs=_candidate(con,channel_id,rig_id,version_id)
        old=con.execute("SELECT 1 FROM artifacts WHERE channel_id=? AND kind='rig_runtime_proof.v1' AND logical_key=?",
                        (channel_id,version_id)).fetchone()
        if old:
            s.error("STALE_HEAD","Candidate proof already committed",409)
        if fresh["project_id"]!=pid or meta["base"]!=metadata["base"]:
            s.error("LINEAGE_MISMATCH","Rig source changed during proof publication",422)
        s.add_artifact(con,aid=aid,channel_id=channel_id,project_id=pid,
            kind="rig_runtime_proof.v1",schema="rig_runtime_proof.v1",
            logical=version_id,revision=1,status="draft",checksum=checksum,size=size,
            relative=path,metadata={"rig_id":rig_id,"rig_version_id":version_id,
                                    "pose_png_sha256":dict(zip(POSES,images)),
                                    "source_version":docs["parts"]["asset_version_id"]})
        return {"rig_version_id":version_id,"proof_artifact_id":aid,
                "pose_png_sha256":dict(zip(POSES,images)),
                "verified_images":len(images)}
    return s.document_publish(doc,path,commit)


def recorded(con,channel_id,rig_id,version_id,pid):
    proof=con.execute("""
        SELECT * FROM artifacts WHERE channel_id=? AND project_id=?
          AND kind='rig_runtime_proof.v1' AND logical_key=?
    """,(channel_id,pid,version_id)).fetchone()
    if proof is None or proof["approval_status"]=="rejected":
        s.error("RIG_RUNTIME_NOT_VERIFIED","Official loader proof not recorded",409)
    path=s.bounded_path(proof["relative_path"])
    if not path.is_file() or s.filehash(path)!=(proof["sha256"],proof["byte_size"]):
        s.error("LINEAGE_MISMATCH","Official loader proof changed after recording",422)
    document=json.loads(path.read_bytes())
    if document["rig_id"]!=rig_id or document["rig_version_id"]!=version_id:
        s.error("LINEAGE_MISMATCH","Runtime proof bound to another rig",422)
    return proof,document


def _candidate_readonly(con,channel_id,rig_id,version_id):
    """Integrity check for an already reviewed rig (no mutation)."""
    return _candidate(con,channel_id,rig_id,version_id,allow_approved=True)
