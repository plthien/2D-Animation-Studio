"""C3 deterministic requirements, same-channel version registry and immutable binding pins."""
from __future__ import annotations
import json
from app.animation import service as s, authoring as a

def requirements(pid: str) -> dict:
    with s.reader() as con:
        pr=a.project(con,pid)
        shot=a.latest(con,pid,"shot-plan")
        if not shot:
            s.error("UNAPPROVED_DEPENDENCY","Approve ShotPlan before resolving assets",422)
        doc=a.verified_doc(shot)
        rows=[]
        for kind,ids in (("actor",doc["actor_ids"]),("prop",doc["prop_ids"]),("location",doc["location_ids"])):
            for ident in sorted(ids):
                usage=sorted(sh["shot_id"] for sh in doc["shots"] if (
                    ident in sh["actor_ids"] if kind=="actor" else
                    ident in sh["prop_ids"] if kind=="prop" else
                    sh["location_id"]==ident))
                if not usage: continue
                rows.append({"requirement_id":"req_"+s.sha({"kind":kind,"key":ident,"view":"front" if kind=="actor" else "default"})[:24],
                             "kind":kind,"semantic_key":ident,"view":"front" if kind=="actor" else "default",
                             "shot_ids":usage,"required_capabilities":[]})
        for loc in sorted({sh["location_id"] for sh in doc["shots"]}):
            rows.append({"requirement_id":"req_"+s.sha({"kind":"background","key":loc})[:24],
                         "kind":"background","semantic_key":loc,"view":"default",
                         "shot_ids":sorted(sh["shot_id"] for sh in doc["shots"] if sh["location_id"]==loc),
                         "required_capabilities":[]})
        inputs={"shot_plan_artifact_id":shot["artifact_id"],"shot_plan_sha256":shot["sha256"],
                "visual_style_hash":s.channel_row(con,pr["channel_id"])["visual_style_hash"]}
        return {"project_id":pid,"channel_id":pr["channel_id"],"source":inputs,
                "fingerprint":s.sha({"inputs":inputs,"requirements":rows}),"requirements":rows}

def versions(channel_id: str,limit: int=100):
    with s.reader() as con:
        s.channel_row(con,channel_id)
        rows=con.execute("""SELECT a.asset_id,a.kind,a.semantic_key,a.view_key,v.asset_version_id,
                v.revision,v.status,v.visual_style_hash,v.capability_hash,v.source_sha256,v.artifact_id,
                v.created_at FROM asset_versions v JOIN assets a ON a.asset_id=v.asset_id
                WHERE a.channel_id=? ORDER BY v.created_at DESC LIMIT ?""",(channel_id,limit)).fetchall()
        return {"items":[s.rowdict(r) for r in rows],"next_cursor":None}

def bindings(pid: str):
    with s.reader() as con:
        a.project(con,pid)
        rows=con.execute("""SELECT b.*,v.status,v.visual_style_hash,v.capability_hash,
                             a.kind,a.semantic_key,a.view_key
                             FROM project_asset_bindings b
                             JOIN asset_versions v ON v.asset_version_id=b.asset_version_id
                             JOIN assets a ON a.asset_id=b.asset_id
                             WHERE b.project_id=? ORDER BY b.usage_key""",(pid,)).fetchall()
        return [s.rowdict(row) for row in rows]

def compatible(req: dict, version, current_style: str) -> bool:
    return (version["status"]=="approved" and version["kind"]==req["kind"]
        and version["semantic_key"]==req["semantic_key"]
        and version["view_key"]==req["view"]
        and version["visual_style_hash"]==current_style
        and not req["required_capabilities"])

def resolution(pid: str):
    needed=requirements(pid)
    with s.reader() as con:
        ch=s.channel_row(con,needed["channel_id"])
        chosen={row["usage_key"]:dict(row) for row in con.execute(
            """SELECT b.*,v.status,v.visual_style_hash,v.capability_hash,a.kind,a.semantic_key,a.view_key
               FROM project_asset_bindings b JOIN asset_versions v ON v.asset_version_id=b.asset_version_id
               JOIN assets a ON a.asset_id=b.asset_id WHERE b.project_id=?""",(pid,))}
        entries=[]
        for r in needed["requirements"]:
            b=chosen.get(r["requirement_id"])
            ok=bool(b and b["source_fingerprint"]==needed["fingerprint"] and compatible(r,b,ch["visual_style_hash"]))
            entries.append({"requirement":r,"binding":b if ok else None,
                            "state":"resolved" if ok else "unresolved",
                            "reason":None if ok else ("STALE_OR_INCOMPATIBLE_PIN" if b else "NO_APPROVED_COMPATIBLE_PIN")})
        return {"requirements_fingerprint":needed["fingerprint"],
                "requirements":entries,"resolved_count":sum(x["state"]=="resolved" for x in entries),
                "total_count":len(entries),"source":needed["source"]}

def bind(pid: str, requirement_id: str, asset_version_id: str, expected_fingerprint: str):
    needed=requirements(pid)
    if expected_fingerprint!=needed["fingerprint"]:
        s.error("STALE_HEAD","Asset requirements changed",current_fingerprint=needed["fingerprint"])
    req=next((r for r in needed["requirements"] if r["requirement_id"]==requirement_id),None)
    if not req: s.error("NOT_FOUND","Requirement not found",404)
    with s.writer() as con:
        pr=a.project(con,pid)
        ch=s.channel_row(con,pr["channel_id"])
        version=con.execute("""SELECT v.*,a.kind,a.semantic_key,a.view_key
            FROM asset_versions v JOIN assets a ON a.asset_id=v.asset_id
            WHERE v.asset_version_id=? AND v.channel_id=?""",
            (asset_version_id,pr["channel_id"])).fetchone()
        if version is None: s.error("NOT_FOUND","Approved channel asset version not found",404)
        if not compatible(req,version,ch["visual_style_hash"]):
            s.error("CAPABILITY_UNSUPPORTED","Version kind, view, style or capability is incompatible",422)
        existing=con.execute("SELECT * FROM project_asset_bindings WHERE project_id=? AND usage_key=?",
                             (pid,requirement_id)).fetchone()
        if existing:
            if existing["asset_version_id"]==asset_version_id and existing["source_fingerprint"]==expected_fingerprint:
                return s.rowdict(existing)
            s.error("STALE_HEAD","Existing exact version pin must be explicitly removed before replacement")
        aid=s.uid("bind")
        t=s.now()
        con.execute("""INSERT INTO project_asset_bindings
                    (binding_id,project_id,channel_id,asset_id,asset_version_id,usage_key,source_fingerprint,created_at,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?)""",
                    (aid,pid,pr["channel_id"],version["asset_id"],asset_version_id,requirement_id,
                     expected_fingerprint,t,t))
        return s.rowdict(con.execute("SELECT * FROM project_asset_bindings WHERE binding_id=?",(aid,)).fetchone())

def unbind(pid: str,binding_id: str,expected_fingerprint: str):
    needed=requirements(pid)
    if expected_fingerprint!=needed["fingerprint"]:
        s.error("STALE_HEAD","Requirements changed")
    with s.writer() as con:
        a.project(con,pid)
        row=con.execute("SELECT * FROM project_asset_bindings WHERE project_id=? AND binding_id=?",
                        (pid,binding_id)).fetchone()
        if not row:s.error("NOT_FOUND","Binding not found",404)
        con.execute("DELETE FROM project_asset_bindings WHERE binding_id=? AND project_id=?",(binding_id,pid))
        return {"removed_binding_id":binding_id}
