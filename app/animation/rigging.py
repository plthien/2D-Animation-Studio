"""C4 durable rig drafts, pixel edits, reviewed sprite export and immutable approvals."""
from __future__ import annotations
import base64
import hashlib
import io
import json
from pathlib import Path

from PIL import Image
from jsonschema import Draft202012Validator, FormatChecker

from app.animation import service as s, authoring as a
from app.animation import rig_pixels as px

SCHEMAS = Path(__file__).resolve().parents[2] / "contracts/animation/schemas"
VALIDATORS = {
    key: Draft202012Validator(json.loads((SCHEMAS / (key + ".schema.json")).read_text()),
                                    format_checker=FormatChecker())
    for key in ("parts_manifest.v1", "rig_profile.v1", "rig_manifest.v1")
}


def _validate(kind: str, obj: dict) -> None:
    issues = sorted(VALIDATORS[kind].iter_errors(obj), key=lambda x: str(x.path))
    if issues:
        s.error("RIG_MANIFEST_INVALID", kind + ": " + issues[0].message, 422)


def _stored(raw: bytes, rel: str) -> str:
    """Immutable name, never overwrite conflicting bytes; integrity is checked after write."""
    dest = s.bounded_path(rel)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        if s.filehash(dest) != (px.digest(raw), len(raw)):
            s.error("LINEAGE_MISMATCH", "Immutable rig file collision", 422)
    else:
        import os
        import tempfile
        folder = s.bounded_path("_staging")
        folder.mkdir(exist_ok=True)
        fd, scratch = tempfile.mkstemp(dir=folder, prefix="rig-")
        try:
            with os.fdopen(fd, "wb") as output:
                output.write(raw)
                output.flush()
                os.fsync(output.fileno())
            if s.filehash(Path(scratch)) != (px.digest(raw), len(raw)):
                s.error("LINEAGE_MISMATCH", "Rig file staging mismatch", 422)
            os.replace(scratch, dest)
        finally:
            Path(scratch).unlink(missing_ok=True)
    return rel


def _record(con, cid, pid, kind, rel, data, *, logical=None, status="draft", revision=1):
    aid = s.uid("ar")
    raw = s.bounded_path(rel).read_bytes()
    s.add_artifact(con, aid=aid, channel_id=cid, project_id=pid, kind=kind,
                   schema=kind, logical=logical or aid, revision=revision,
                   status=status, checksum=px.digest(raw), size=len(raw), relative=rel,
                   metadata=data)
    return aid


def _source(con, pid, version):
    pr = a.project(con, pid)
    row = con.execute("""
        SELECT v.*, a.kind, ar.metadata_json FROM asset_versions v
        JOIN assets a ON a.asset_id=v.asset_id
        JOIN artifacts ar ON ar.artifact_id=v.artifact_id
        WHERE v.asset_version_id=? AND v.channel_id=? AND v.status='approved'
    """, (version, pr["channel_id"])).fetchone()
    if not row or row["kind"] != "actor":
        s.error("RIG_SOURCE_NOT_APPROVED", "Select an approved actor image in the same channel", 422)
    ch = s.channel_row(con, pr["channel_id"])
    if row["visual_style_hash"] != ch["visual_style_hash"]:
        s.error("RIG_SOURCE_STALE", "Source visual style is no longer current", 409)
    meta = json.loads(row["metadata_json"])
    src = con.execute("SELECT * FROM artifacts WHERE artifact_id=? AND channel_id=?",
                      (meta["source_image_artifact_id"], pr["channel_id"])).fetchone()
    if not src:
        s.error("LINEAGE_MISMATCH", "Source artifact is missing", 422)
    path = s.bounded_path(src["relative_path"])
    if not path.is_file() or s.filehash(path) != (src["sha256"], src["byte_size"]) or src["sha256"] != row["source_sha256"]:
        s.error("LINEAGE_MISMATCH", "Source image changed on disk", 422)
    return pr, row, path


def _draft(con, pid, rig_id):
    pr = a.project(con, pid)
    row = con.execute("SELECT * FROM rigs WHERE rig_id=? AND channel_id=?",
                      (rig_id, pr["channel_id"])).fetchone()
    if row is None:
        s.error("NOT_FOUND", "Rig not found in project channel", 404)
    # The same-channel asset may be reused; drafts remain bound to their initiating project.
    art = con.execute("""
        SELECT * FROM artifacts WHERE channel_id=? AND project_id=?
          AND kind='c4.rig_draft.v1' AND logical_key=?
        ORDER BY revision DESC LIMIT 1
    """, (pr["channel_id"], pid, rig_id)).fetchone()
    if art is None:
        s.error("NOT_FOUND", "Project rig draft does not exist", 404)
    path = s.bounded_path(art["relative_path"])
    if not path.is_file() or s.filehash(path) != (art["sha256"], art["byte_size"]):
        s.error("LINEAGE_MISMATCH", "Rig draft changed or disappeared", 422)
    return pr, row, art, json.loads(path.read_bytes())


def _publish_draft(pid, rig_id, doc, expected_revision, *, create=False):
    aid = s.uid("ar")
    rel = f"rigs/{rig_id}/drafts/{aid}.json"
    def callback(con, checksum, size):
        pr = a.project(con, pid)
        old = con.execute("""
            SELECT MAX(revision) AS revision FROM artifacts
            WHERE channel_id=? AND project_id=? AND kind='c4.rig_draft.v1'
              AND logical_key=?""", (pr["channel_id"], pid, rig_id)).fetchone()["revision"] or 0
        if old != expected_revision:
            s.error("STALE_HEAD", "Rig draft changed; reopen before saving",
                    current_revision=old)
        s.add_artifact(con, aid=aid, channel_id=pr["channel_id"], project_id=pid,
                       kind="c4.rig_draft.v1", schema="c4.rig_draft.v1",
                       logical=rig_id, revision=old+1, status="draft",
                       checksum=checksum, size=size, relative=rel,
                       metadata={"source_version":doc["source_version"],
                                 "style_hash":doc["style_hash"]})
        return {"rig_id":rig_id, "draft_revision":old+1}
    return s.document_publish(doc, rel, callback)


def start(pid, version):
    with s.reader() as con:
        pr, source, path = _source(con, pid, version)
        asset_id = source["asset_id"]
        existing = con.execute("SELECT * FROM rigs WHERE asset_id=? AND semantic_key='humanoid'",
                               (asset_id,)).fetchone()
        rig_id = existing["rig_id"] if existing else s.uid("rg")
        prior = con.execute("SELECT 1 FROM artifacts WHERE channel_id=? AND project_id=? AND kind='c4.rig_draft.v1' AND logical_key=?",
                            (pr["channel_id"], pid, rig_id)).fetchone()
        if prior:
            s.error("RIG_DRAFT_EXISTS", "Reopen the existing rig draft instead", 409)
        source_sha = source["source_sha256"]
        style_hash = source["visual_style_hash"]
        raw = path.read_bytes()
    try:
        original = px.load_rgba(raw)
        parts, masks = px.extract(original)
    except ValueError as exc:
        s.error("RIG_EXTRACTION_FAILED", str(exc), 422)
    mask_refs = {}
    for role, mask in masks.items():
        b = px.png_bytes(mask)
        rel = f"rigs/{rig_id}/masks/{role}/{px.digest(b)}.png"
        _stored(b, rel)
        mask_refs[role] = rel
    for role, p in parts.items():
        p["mask"] = mask_refs[role]
        p["replacement"] = None
    doc = {"source_version":version, "source_sha":source_sha,
           "style_hash":style_hash, "size":list(original.size), "parts":parts}
    with s.writer() as con:
        pr, source, check = _source(con, pid, version)
        if source["source_sha256"] != source_sha or source["visual_style_hash"] != style_hash:
            s.error("STALE_HEAD", "Source changed during extraction")
        if con.execute("SELECT 1 FROM rigs WHERE rig_id=?", (rig_id,)).fetchone() is None:
            t = s.now()
            con.execute("INSERT INTO rigs VALUES (?,?,?,?,?,?)",
                        (rig_id, pr["channel_id"], source["asset_id"], "humanoid", t, t))
    return _publish_draft(pid, rig_id, doc, 0)


def view(pid, rig_id):
    with s.reader() as con:
        pr, rig, art, doc = _draft(con, pid, rig_id)
        _source(con, pid, doc["source_version"])
        return {"rig_id":rig_id, "draft_revision":art["revision"], **doc}


def list_rigs(pid):
    with s.reader() as con:
        pr = a.project(con, pid)
        rows = con.execute("""
            SELECT r.*,v.rig_version_id,v.status,v.revision
            FROM rigs r LEFT JOIN rig_versions v ON v.rig_id=r.rig_id
            WHERE r.channel_id=? ORDER BY r.created_at,v.revision
        """, (pr["channel_id"],)).fetchall()
        return {"items":[dict(x) for x in rows]}


def edit(pid, rig_id, role, expected_revision, strokes=None,
         pivot=None, layer=None, reviewed=None, reset=False):
    if role not in px.ROLES:
        s.error("VALIDATION_FAILED", "Unknown sprite role", 422)
    with s.reader() as con:
        pr, rig, art, doc = _draft(con, pid, rig_id)
        if art["revision"] != expected_revision:
            s.error("STALE_HEAD", "Rig draft revision changed")
        _, source, src = _source(con, pid, doc["source_version"])
        if source["source_sha256"] != doc["source_sha"] or source["visual_style_hash"] != doc["style_hash"]:
            s.error("RIG_SOURCE_STALE", "Source lineage is stale")
        doc = json.loads(json.dumps(doc))
    part = doc["parts"][role]
    if reset:
        original = px.load_rgba(src.read_bytes())
        proposals, masks = px.extract(original)
        part.update(proposals[role])
        mask_bytes = px.png_bytes(masks[role])
        path = f"rigs/{rig_id}/masks/{role}/{px.digest(mask_bytes)}.png"
        _stored(mask_bytes, path)
        part["mask"],part["replacement"] = path,None
    if strokes:
        mask = Image.open(s.bounded_path(part["mask"])).convert("L")
        try:
            mask = px.apply_strokes(mask, strokes)
        except (ValueError, KeyError, TypeError) as exc:
            s.error("VALIDATION_FAILED", "Invalid mask brush action: " + str(exc), 422)
        mask_bytes = px.png_bytes(mask)
        path = f"rigs/{rig_id}/masks/{role}/{px.digest(mask_bytes)}.png"
        _stored(mask_bytes, path)
        part["mask"],part["provenance"],part["reviewed"] = path,"manual_brush",False
    if pivot is not None:
        if set(pivot) != {"x", "y"} or any(type(pivot[k]) not in (int,float) or not 0 <= pivot[k] <= 1 for k in pivot):
            s.error("VALIDATION_FAILED", "Pivot must be normalized x/y", 422)
        part["pivot"]={"x":pivot["x"],"y":pivot["y"],"coordinate_system":"normalized_top_left"}
        part["reviewed"] = False
    if layer is not None:
        if type(layer) is not int or not 0 <= layer <= 100:
            s.error("VALIDATION_FAILED", "Layer must be an integer 0..100", 422)
        part["layer"],part["reviewed"] = layer,False
    if reviewed is not None:
        if type(reviewed) is not bool:
            s.error("VALIDATION_FAILED", "reviewed must be boolean", 422)
        part["reviewed"] = reviewed
    if part["reviewed"]:
        raw = get_sprite_bytes(pid, rig_id, role, document=doc, source_path=src)
        try:
            px.bounds_for_sprite(raw)
        except ValueError as exc:
            s.error("RIG_REQUIRED_PART_EMPTY", f"{role}: {exc}", 422)
    return _publish_draft(pid, rig_id, doc, expected_revision)


def replace(pid, rig_id, role, expected_revision, raw):
    if role not in px.ROLES:
        s.error("VALIDATION_FAILED", "Unknown sprite role", 422)
    if len(raw) > 12 * 1024 * 1024 or not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        s.error("VALIDATION_FAILED", "Supply a PNG no larger than 12 MiB", 422)
    try:
        original = px.load_rgba(raw)
        if original.getchannel("A").getextrema()[0] == 255:
            raise ValueError("Replacement needs actual transparency")
        px.bounds_for_sprite(px.png_bytes(original))
    except (ValueError, OSError) as exc:
        s.error("VALIDATION_FAILED", f"Invalid replacement PNG: {exc}", 422)
    with s.reader() as con:
        _,_,art,doc = _draft(con,pid,rig_id)
        if art["revision"] != expected_revision:
            s.error("STALE_HEAD", "Rig draft changed")
    filename = f"rigs/{rig_id}/replacements/{role}/{px.digest(raw)}.png"
    _stored(raw,filename)
    doc["parts"][role].update({"replacement":filename,"provenance":"manual_replacement",
                                "reviewed":False,"uncertain":False,"occluded":False})
    return _publish_draft(pid,rig_id,doc,expected_revision)


def get_sprite_bytes(pid,rig_id,role,*,document=None,source_path=None):
    if role not in px.ROLES:
        s.error("VALIDATION_FAILED", "Unknown part", 422)
    if document is None:
        with s.reader() as con:
            _,_,_,document = _draft(con,pid,rig_id)
            _,_,source_path = _source(con,pid,document["source_version"])
    part=document["parts"][role]
    if part["replacement"]:
        raw=s.bounded_path(part["replacement"]).read_bytes()
        px.bounds_for_sprite(raw)
        return raw
    original=px.load_rgba(source_path.read_bytes())
    mask_path=s.bounded_path(part["mask"])
    mask=Image.open(mask_path).convert("L")
    if mask.size!=original.size:
        s.error("LINEAGE_MISMATCH", "Mask dimensions changed",422)
    return px.png_bytes(px.sprite(original,mask))


def binary(pid,rig_id,role,kind):
    if kind not in ("mask","sprite"):
        s.error("VALIDATION_FAILED", "Invalid image kind",422)
    if role not in px.ROLES:
        s.error("VALIDATION_FAILED", "Unknown part role",422)
    with s.reader() as con:
        _,_,_,doc=_draft(con,pid,rig_id)
        if kind=="mask":
            raw=s.bounded_path(doc["parts"][role]["mask"]).read_bytes()
            return raw
    return get_sprite_bytes(pid,rig_id,role)


def export(pid,rig_id,expected_revision):
    with s.reader() as con:
        pr, rig, art, doc=_draft(con,pid,rig_id)
        if art["revision"]!=expected_revision:
            s.error("STALE_HEAD", "Draft changed before export")
        _, source, path=_source(con,pid,doc["source_version"])
        if source["source_sha256"]!=doc["source_sha"] or source["visual_style_hash"]!=doc["style_hash"]:
            s.error("RIG_SOURCE_STALE","Source image or style differs",409)
        missing=[role for role in px.ROLES if not doc["parts"][role]["reviewed"]]
        if missing:
            s.error("RIG_PARTS_NOT_REVIEWED","Review every semantic part before export",422,roles=missing)
    pngs={}
    for role in px.ROLES:
        pngs[role]=get_sprite_bytes(pid,rig_id,role,document=doc,source_path=path)
        try:
            px.bounds_for_sprite(pngs[role])
        except ValueError as exc:
            s.error("RIG_REQUIRED_PART_EMPTY",role+": "+str(exc),422)
    try:
        skeleton,atlas,page=px.spine_package(pngs,doc["parts"])
    except ValueError as exc:
        s.error("RIG_EXPORT_INVALID",str(exc),422)
    # Export files are content-addressed; old approved rig assets are never mutated.
    revision=1
    with s.reader() as con:
        revision=con.execute("SELECT COALESCE(MAX(revision),0)+1 FROM rig_versions WHERE rig_id=?",
                             (rig_id,)).fetchone()[0]
    version=s.uid("rv")
    base=f"rigs/{rig_id}/versions/{version}"
    _stored(skeleton,base+"/skeleton.json")
    _stored(atlas,base+"/skeleton.atlas")
    _stored(page,base+"/page.png")
    for role in px.ROLES:
        _stored(pngs[role],base+f"/{role}.png")
    profile_id=s.uid("ar")
    parts_id=s.uid("ar")
    manifest_id=s.uid("ar")
    t=s.now()
    parts_doc={
        "schema_version":"parts_manifest.v1","artifact_id":parts_id,
        "channel_id":pr["channel_id"],"project_id":pid,"revision":revision,
        "created_at":t,"asset_version_id":doc["source_version"],
        "source_image_sha256":doc["source_sha"],
        "parts":[{
            "role":role,"sprite_artifact_id":s.uid("ar"),
            "png_sha256":px.digest(pngs[role]),
            "mask_sha256":px.digest(s.bounded_path(doc["parts"][role]["mask"]).read_bytes()),
            "pivot":doc["parts"][role]["pivot"],"reviewed":True
        } for role in px.ROLES]
    }
    profile={
        "schema_version":"rig_profile.v1","artifact_id":profile_id,
        "channel_id":pr["channel_id"],"revision":revision,
        "created_at":t,"parts_manifest_artifact_id":parts_id,
        "bones":[{"role":role,"runtime_bone":role} for role in px.BONES],
        "capabilities":["idle"],
    }
    manifest={
        "schema_version":"rig_manifest.v1","artifact_id":manifest_id,
        "channel_id":pr["channel_id"],"revision":revision,"created_at":t,
        "rig_version_id":version,"parts_manifest_artifact_id":parts_id,
        "rig_profile_artifact_id":profile_id,"spine_data_version":"4.2",
        "runtime_package":"@esotericsoftware/spine-pixi-v8",
        "runtime_version":"4.2.120","pixi_version":"8.16.0",
        "skeleton_sha256":px.digest(skeleton),"atlas_sha256":px.digest(atlas)
    }
    for kind,d in (("parts_manifest.v1",parts_doc),("rig_profile.v1",profile),("rig_manifest.v1",manifest)):
        _validate(kind,d)
    for k,d in (("parts",parts_doc),("profile",profile),("manifest",manifest)):
        _stored(s.canon(d),base+"/"+k+".json")
    with s.writer() as con:
        pr2, rig2, art2, doc2=_draft(con,pid,rig_id)
        if art2["revision"]!=expected_revision or doc2!=doc or s.channel_row(con,pr["channel_id"])["visual_style_hash"]!=doc["style_hash"]:
            s.error("STALE_HEAD","Draft or style changed before publish")
        actual=con.execute("SELECT COALESCE(MAX(revision),0)+1 FROM rig_versions WHERE rig_id=?",
                           (rig_id,)).fetchone()[0]
        if actual!=revision:
            s.error("STALE_HEAD","Rig candidate version changed")
        for role,row in zip(px.ROLES,parts_doc["parts"]):
            rel=base+f"/{role}.png"
            aid=row["sprite_artifact_id"]
            raw=pngs[role]
            s.add_artifact(con,aid=aid,channel_id=pr["channel_id"],project_id=pid,
                kind="rig_sprite.v1",schema="image/png",logical=version+":"+role,
                revision=1,status="draft",checksum=px.digest(raw),size=len(raw),
                relative=rel,metadata={"rig_version_id":version,"role":role})
        for kind,aid,key in (("parts_manifest.v1",parts_id,"parts"),
                              ("rig_profile.v1",profile_id,"profile"),
                              ("rig_manifest.v1",manifest_id,"manifest")):
            raw=s.canon({"parts":parts_doc,"profile":profile,"manifest":manifest}[key])
            s.add_artifact(con,aid=aid,channel_id=pr["channel_id"],project_id=pid,
                kind=kind,schema=kind,logical=rig_id,revision=revision,
                status="draft",checksum=px.digest(raw),size=len(raw),
                relative=base+"/"+key+".json",
                metadata={"rig_version_id":version,"draft_revision":expected_revision,
                          "source_version":doc["source_version"],"style_hash":doc["style_hash"],
                          "base":base})
        con.execute("INSERT INTO rig_versions VALUES (?,?,?,?,?,?,?,?,?)",
                    (version,rig_id,pr["channel_id"],revision,manifest_id,profile_id,
                     "candidate",s.sha(profile["capabilities"]),t,None))
    return {"rig_id":rig_id,"rig_version_id":version,"revision":revision,
            "candidate":True,"loader_verified":False,"manifest":manifest}


def file_for_version(cid,rig_id,version,filename):
    allowed={"skeleton.json","skeleton.atlas","page.png","parts.json","profile.json","manifest.json"}
    if filename not in allowed:
        s.error("NOT_FOUND","Unknown rig output file",404)
    with s.reader() as con:
        row=con.execute("""
        SELECT rv.*,ar.metadata_json FROM rig_versions rv JOIN rigs r ON r.rig_id=rv.rig_id
        JOIN artifacts ar ON ar.artifact_id=rv.rig_manifest_artifact_id
        WHERE rv.rig_version_id=? AND rv.rig_id=? AND rv.channel_id=?
        """,(version,rig_id,cid)).fetchone()
        if not row:
            s.error("NOT_FOUND","Rig version not found",404)
        meta=json.loads(row["metadata_json"])
        path=s.bounded_path(meta["base"]+"/"+filename)
        if not path.is_file():
            s.error("LINEAGE_MISMATCH","Exported file missing",422)
        if filename in ("skeleton.json","skeleton.atlas"):
            manifest=json.loads(s.bounded_path(meta["base"]+"/manifest.json").read_bytes())
            if px.digest(path.read_bytes())!=manifest["skeleton_sha256" if filename.endswith(".json") else "atlas_sha256"]:
                s.error("LINEAGE_MISMATCH","Skeleton/atlas digest mismatch",422)
        return path


def approve(cid,rig_id,version,decision,expected_revision,loader_evidence=None):
    if decision not in ("approved","rejected"):
        s.error("VALIDATION_FAILED","Invalid review decision",422)
    # IMPORTANT: Browser-supplied evidence cannot prove official Spine loading.
    # Until a trustworthy real loader verification is wired, approval FAILS CLOSED.
    if decision=="approved":
        s.error("RIG_RUNTIME_NOT_VERIFIED",
                "Official Spine/Pixi runtime acceptance evidence is not yet trusted by backend",409)
    with s.writer() as con:
        record=con.execute("SELECT * FROM rig_versions WHERE rig_id=? AND rig_version_id=? AND channel_id=?",
                           (rig_id,version,cid)).fetchone()
        if not record:
            s.error("NOT_FOUND","Rig version not found",404)
        if record["status"]!="candidate" or record["revision"]!=expected_revision:
            s.error("STALE_HEAD","Rig candidate changed")
        con.execute("UPDATE rig_versions SET status='rejected',reviewed_at=? WHERE rig_version_id=?",
                    (s.now(),version))
        return {"rig_version_id":version,"status":"rejected"}
