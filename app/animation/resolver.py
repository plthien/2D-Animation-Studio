"""C3 deterministic requirements, same-channel version registry and immutable binding pins."""
from __future__ import annotations
import json
from app.animation import service as s, authoring as a



def current_shot(con, pid: str):
    """Reject superseded upstream revisions before a requirement may be used."""
    shot=a.latest(con,pid,"shot-plan")
    if shot is None:
        s.error("UNAPPROVED_DEPENDENCY","Current approved ShotPlan required",422)
    doc=a.verified_doc(shot)
    script=a.latest(con,pid,"script")
    ideas=a.latest(con,pid,"topic-ideas")
    if script is None or ideas is None:
        s.error("UNAPPROVED_DEPENDENCY","Approved Topic and Script required",422)
    script_doc=a.verified_doc(script)
    if (script_doc.get("topic_ideas_artifact_id")!=ideas["artifact_id"]
        or doc.get("script_artifact_id")!=script["artifact_id"]
        or doc.get("script_sha256")!=script["sha256"]):
        s.error("STALE_HEAD","ShotPlan references a superseded authoring source",
                current_script_artifact_id=script["artifact_id"])
    original=json.loads(shot["metadata_json"]).get("source_fingerprint")
    _,_,_,current,_=a.source(con,pid,"shot-plan")
    if original!=current:
        s.error("STALE_HEAD","ShotPlan reservation source no longer current",current_fingerprint=current)
    return shot

def requirements(pid: str) -> dict:
    with s.reader() as con:
        pr=a.project(con,pid)
        shot=current_shot(con,pid)
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
                "total_count":len(entries),"source":needed["source"],
                "compatible_versions":{r["requirement_id"]:[v["asset_version_id"] for v in con.execute("""
                   SELECT v.asset_version_id,v.status,v.visual_style_hash,v.capability_hash,
                          a.kind,a.semantic_key,a.view_key FROM asset_versions v
                   JOIN assets a ON a.asset_id=v.asset_id
                   WHERE a.channel_id=? AND v.status='approved'""", (needed["channel_id"],))
                   if compatible(r,v,ch["visual_style_hash"])] for r in needed["requirements"]},
                "rig_capability_status":"pending_c4_rig_validation"}

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


# Published resolver authorities: requests are idempotent by complete input fingerprint.
def publish_requirements(pid: str) -> dict:
    need=requirements(pid)
    with s.reader() as con:
        old=con.execute("""SELECT * FROM artifacts WHERE project_id=? AND kind='asset_requirements.v1'
           AND json_extract(metadata_json,'$.source_fingerprint')=? ORDER BY revision DESC LIMIT 1""",
           (pid,need["fingerprint"])).fetchone()
        if old: return s.artifact_view(old)
        revision=con.execute("""SELECT COALESCE(MAX(revision),0)+1 FROM artifacts
           WHERE project_id=? AND kind='asset_requirements.v1'""",(pid,)).fetchone()[0]
    aid=s.uid("ar")
    doc={"schema_version":"asset_requirements.v1","artifact_id":aid,"channel_id":need["channel_id"],
         "project_id":pid,"revision":revision,"created_at":s.now(),
         "shot_plan_artifact_id":need["source"]["shot_plan_artifact_id"],
         "requirements":need["requirements"]}
    rel=f"projects/{pid}/resolver/requirements/{aid}.json"
    def commit(con,digest,size):
        current=requirements(pid)
        if current["fingerprint"]!=need["fingerprint"]:
            s.error("STALE_HEAD","Asset requirements changed during publication")
        duplicate=con.execute("""SELECT * FROM artifacts WHERE project_id=? AND kind='asset_requirements.v1'
            AND json_extract(metadata_json,'$.source_fingerprint')=?""",
            (pid,need["fingerprint"])).fetchone()
        if duplicate:return s.artifact_view(duplicate)
        next_revision=con.execute("""SELECT COALESCE(MAX(revision),0)+1 FROM artifacts
            WHERE project_id=? AND kind='asset_requirements.v1'""",(pid,)).fetchone()[0]
        if next_revision!=revision:s.error("STALE_HEAD","Requirements revision race")
        s.add_artifact(con,aid=aid,channel_id=need["channel_id"],project_id=pid,
            kind="asset_requirements.v1",schema="asset_requirements.v1",logical="asset_requirements",
            revision=revision,status="approved",checksum=digest,size=size,relative=rel,
            metadata={"source_fingerprint":need["fingerprint"]})
        con.execute("UPDATE artifacts SET source_fingerprints_json=?,parents_json=? WHERE artifact_id=?",
            (s.canon(need["source"]).decode(),s.canon([need["source"]["shot_plan_artifact_id"]]).decode(),aid))
        return s.artifact_view(con.execute("SELECT * FROM artifacts WHERE artifact_id=?",(aid,)).fetchone())
    return s.document_publish(doc,rel,commit)


def publish_resolution(pid: str) -> dict | None:
    state=resolution(pid)
    if state["resolved_count"]!=state["total_count"]:return None
    requirements_artifact=publish_requirements(pid)
    pins=[]
    with s.reader() as con:
        for entry in state["requirements"]:
            b=entry["binding"]
            v=con.execute("""SELECT v.*,a.kind,a.semantic_key,a.view_key FROM asset_versions v
                              JOIN assets a ON a.asset_id=v.asset_id WHERE v.asset_version_id=?""",
                          (b["asset_version_id"],)).fetchone()
            pins.append({"requirement_id":entry["requirement"]["requirement_id"],
             "asset_version_id":v["asset_version_id"],"asset_channel_id":requirements_artifact["channel_id"],
             "kind":v["kind"],"semantic_key":v["semantic_key"],"view":v["view_key"],
             "visual_style_hash":v["visual_style_hash"],"capability_hash":v["capability_hash"],
             "approval_status":"approved"})
        key=s.sha({"requirements_sha":requirements_artifact["sha256"],"pins":pins})
        old=con.execute("""SELECT * FROM artifacts WHERE project_id=? AND kind='asset_resolution.v1'
            AND json_extract(metadata_json,'$.source_fingerprint')=?""",(pid,key)).fetchone()
        if old:return s.artifact_view(old)
        revision=con.execute("""SELECT COALESCE(MAX(revision),0)+1 FROM artifacts
          WHERE project_id=? AND kind='asset_resolution.v1'""",(pid,)).fetchone()[0]
    aid=s.uid("ar")
    doc={"schema_version":"asset_resolution.v1","artifact_id":aid,
         "channel_id":requirements_artifact["channel_id"],"project_id":pid,
         "revision":revision,"created_at":s.now(),
         "requirements_artifact_id":requirements_artifact["artifact_id"],"pins":pins}
    rel=f"projects/{pid}/resolver/resolutions/{aid}.json"
    def commit(con,digest,size):
        if resolution(pid)["resolved_count"]!=state["total_count"]:
            s.error("STALE_HEAD","Pins changed during resolution publication")
        old=con.execute("""SELECT * FROM artifacts WHERE project_id=? AND kind='asset_resolution.v1'
            AND json_extract(metadata_json,'$.source_fingerprint')=?""",(pid,key)).fetchone()
        if old:return s.artifact_view(old)
        s.add_artifact(con,aid=aid,channel_id=requirements_artifact["channel_id"],project_id=pid,
            kind="asset_resolution.v1",schema="asset_resolution.v1",logical="asset_resolution",
            revision=revision,status="approved",checksum=digest,size=size,relative=rel,
            metadata={"source_fingerprint":key})
        con.execute("UPDATE artifacts SET parents_json=?,source_fingerprints_json=? WHERE artifact_id=?",
           (s.canon([requirements_artifact["artifact_id"]]).decode(),
            s.canon({"requirements":state["requirements_fingerprint"]}).decode(),aid))
        head=con.execute("SELECT revision FROM project_stage_heads WHERE project_id=? AND stage_key='resolver'",(pid,)).fetchone()
        con.execute("""UPDATE project_stage_heads SET artifact_id=?,approval_status='approved',
            revision=revision+1,dependency_fingerprint=?,updated_at=?
            WHERE project_id=? AND stage_key='resolver' AND revision=?""",
            (aid,key,s.now(),pid,head["revision"]))
        return s.artifact_view(con.execute("SELECT * FROM artifacts WHERE artifact_id=?",(aid,)).fetchone())
    return s.document_publish(doc,rel,commit)
