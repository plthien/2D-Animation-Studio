"""C3 managed local-image ingestion and review; no paid provider calls."""
from __future__ import annotations
import hashlib
import io
import json
import os
import tempfile
from pathlib import Path
from PIL import Image, UnidentifiedImageError
from app.animation import service as s, authoring as a

MAX_BYTES=12*1024*1024
MAX_PIXELS=32_000_000
EXT={"PNG":"png","JPEG":"jpg","WEBP":"webp"}

def ingest(pid:str,kind:str,semantic_key:str,view:str,raw:bytes,filename:str) -> dict:
    if kind not in ("actor","prop","location","background"):
        s.error("VALIDATION_FAILED","Invalid asset kind",422)
    if not 1<=len(semantic_key)<=200 or not 1<=len(view)<=100:
        s.error("VALIDATION_FAILED","Invalid semantic key/view",422)
    if len(raw)>MAX_BYTES or len(raw)==0:
        s.error("IMPORT_TOO_LARGE","Image size outside allowed range",413)
    try:
        with Image.open(io.BytesIO(raw)) as im:
            if im.format not in EXT:
                s.error("VALIDATION_FAILED","Unsupported image format",422)
            width,height=im.size
            if width<1 or height<1 or width>16384 or height>16384 or width*height>MAX_PIXELS:
                s.error("VALIDATION_FAILED","Invalid image dimensions",422)
            fmt=im.format
            im.verify()
        with Image.open(io.BytesIO(raw)) as im:
            im.load()
    except (UnidentifiedImageError,OSError,ValueError,Image.DecompressionBombError):
        s.error("VALIDATION_FAILED","Malformed image bytes",422)
    with s.reader() as con:
        pr=a.project(con,pid)
        ch=s.channel_row(con,pr["channel_id"])
        fingerprint=ch["visual_style_hash"]
    digest=hashlib.sha256(raw).hexdigest()
    aid=s.uid("ar")
    ver=s.uid("av")
    image_id=s.uid("ar")
    rel=f"channels/{pr['channel_id']}/images/{digest[:2]}/{image_id}.{EXT[fmt]}"
    target=s.bounded_path(rel)
    target.parent.mkdir(parents=True,exist_ok=True)
    s.bounded_path(rel)
    staging=s.bounded_path("_staging")
    staging.mkdir(parents=True,exist_ok=True)
    fd,scratch=tempfile.mkstemp(prefix="image-",dir=staging)
    try:
        with os.fdopen(fd,"wb") as out:
            out.write(raw);out.flush();os.fsync(out.fileno())
        if s.filehash(Path(scratch))!=(digest,len(raw)):
            s.error("LINEAGE_MISMATCH","Image staging checksum mismatch",422)
        os.replace(scratch,target)
        try:
            with s.writer() as con:
                pr=a.project(con,pid)
                ch=s.channel_row(con,pr["channel_id"])
                if ch["visual_style_hash"]!=fingerprint:
                    s.error("STALE_HEAD","Visual style changed during image upload")
                asset=con.execute("""SELECT * FROM assets
                    WHERE channel_id=? AND kind=? AND semantic_key=? AND view_key=?""",
                    (pr["channel_id"],kind,semantic_key,view)).fetchone()
                asset_id=asset["asset_id"] if asset else s.uid("as")
                t=s.now()
                if not asset:
                    con.execute("INSERT INTO assets VALUES (?,?,?,?,?,?,?)",
                                (asset_id,pr["channel_id"],kind,semantic_key,view,t,t))
                revision=con.execute("SELECT COALESCE(MAX(revision),0)+1 FROM asset_versions WHERE asset_id=?",
                                     (asset_id,)).fetchone()[0]
                s.add_artifact(con,aid=image_id,channel_id=pr["channel_id"],project_id=None,
                  kind="asset_source_image.v1",schema="image/"+("jpeg" if fmt=="JPEG" else fmt.lower()),
                  logical=image_id,revision=1,status="draft",checksum=digest,size=len(raw),relative=rel,
                  metadata={"filename":Path(filename).name[:200],"width":width,"height":height,
                            "origin":"local-user-import","project_id":pid})
                metadata={"schema_version":"asset_version.v1","artifact_id":aid,"asset_id":asset_id,
                   "channel_id":pr["channel_id"],"revision":revision,"created_at":t,
                   "kind":kind,"semantic_key":semantic_key,"view":view,
                   "source_sha256":digest,"width":width,"height":height,
                   "visual_style_hash":fingerprint,"capability_hash":s.sha([]),
                   "approval_status":"candidate"}
                meta_rel=f"channels/{pr['channel_id']}/asset_versions/{aid}.json"
                meta_path=s.bounded_path(meta_rel)
                meta_path.parent.mkdir(parents=True,exist_ok=True)
                data=s.canon(metadata)
                with meta_path.open("xb") as out:
                    out.write(data);out.flush();os.fsync(out.fileno())
                s.add_artifact(con,aid=aid,channel_id=pr["channel_id"],project_id=None,
                    kind="asset_version.v1",schema="asset_version.v1",logical=asset_id,
                    revision=revision,status="draft",checksum=hashlib.sha256(data).hexdigest(),
                    size=len(data),relative=meta_rel,metadata={"source_image_artifact_id":image_id,"project_id":pid})
                con.execute("INSERT INTO asset_versions VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (ver,asset_id,pr["channel_id"],revision,aid,fingerprint,s.sha([]),
                     "candidate",digest,t,None))
                return {"asset_version_id":ver,"asset_id":asset_id,"artifact_id":aid,
                        "source_image_artifact_id":image_id,"width":width,"height":height,
                        "status":"candidate","source_sha256":digest}
        except BaseException:
            # Preserve bytes if a DB record already references them.
            with s.reader() as con:
                if not con.execute("SELECT 1 FROM artifacts WHERE artifact_id=?",(image_id,)).fetchone():
                    target.unlink(missing_ok=True)
            raise
    finally:
        Path(scratch).unlink(missing_ok=True)

def review(pid:str,version_id:str,decision:str):
    if decision not in ("approved","rejected"):
        s.error("VALIDATION_FAILED","Decision must be approved or rejected",422)
    with s.writer() as con:
        pr=a.project(con,pid)
        v=con.execute("""SELECT v.*,a.kind FROM asset_versions v
            JOIN assets a ON a.asset_id=v.asset_id
            JOIN artifacts ar ON ar.artifact_id=v.artifact_id
            WHERE v.asset_version_id=? AND v.channel_id=? AND
                 json_extract(ar.metadata_json,'$.project_id')=?""",
            (version_id,pr["channel_id"],pid)).fetchone()
        if not v:s.error("NOT_FOUND","Candidate not found in this project",404)
        if v["status"]!="candidate":
            s.error("STALE_HEAD","Candidate already reviewed")
        artifact=con.execute("SELECT * FROM artifacts WHERE artifact_id=?",(v["artifact_id"],)).fetchone()
        meta=json.loads(artifact["metadata_json"])
        src=con.execute("SELECT * FROM artifacts WHERE artifact_id=?",
                        (meta["source_image_artifact_id"],)).fetchone()
        for r in (artifact,src):
            p=s.bounded_path(r["relative_path"])
            if not p.is_file() or s.filehash(p)!=(r["sha256"],r["byte_size"]):
                s.error("LINEAGE_MISMATCH","Asset files corrupted",422)
        ch=s.channel_row(con,pr["channel_id"])
        if decision=="approved" and ch["visual_style_hash"]!=v["visual_style_hash"]:
            s.error("STALE_HEAD","Visual style changed")
        con.execute("UPDATE asset_versions SET status=?,reviewed_at=? WHERE asset_version_id=?",
                    (decision,s.now(),version_id))
        con.execute("UPDATE artifacts SET approval_status=?,reviewed_by='local-user',reviewed_at=? WHERE artifact_id IN (?,?)",
                    ("approved" if decision=="approved" else "rejected",s.now(),v["artifact_id"],src["artifact_id"]))
        return {"asset_version_id":version_id,"status":decision,"source_sha256":v["source_sha256"]}

def read_image(pid:str,version_id:str):
    with s.reader() as con:
        pr=a.project(con,pid)
        row=con.execute("""SELECT src.* FROM asset_versions v
            JOIN artifacts ar ON ar.artifact_id=v.artifact_id
            JOIN artifacts src ON src.artifact_id=json_extract(ar.metadata_json,'$.source_image_artifact_id')
            WHERE v.asset_version_id=? AND v.channel_id=?""",(version_id,pr["channel_id"])).fetchone()
        if not row:s.error("NOT_FOUND","Image not found",404)
        path=s.bounded_path(row["relative_path"])
        if not path.is_file() or s.filehash(path)!=(row["sha256"],row["byte_size"]):
            s.error("LINEAGE_MISMATCH","Image bytes mismatch",422)
        return path,row["schema_version"]
