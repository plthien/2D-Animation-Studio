"""C4 project-owned immutable actor-to-rig selections.

A channel rig is reusable; a project's exact resolver actor pins are not.
No new SQLite tables are introduced. Every write is a CAS revisioned artifact.
"""
from __future__ import annotations

import json
from app.animation import service as s, authoring as a, resolver
from app.animation import rig_proof


KIND="project_rig_resolution.v1"
KEY="actor-rig-selection"


def _latest(con,pid,cid):
    return con.execute("""SELECT * FROM artifacts WHERE project_id=? AND channel_id=?
        AND kind=? AND logical_key=? ORDER BY revision DESC LIMIT 1""",
        (pid,cid,KIND,KEY)).fetchone()


def _document(art):
    if not art:
        return None
    path=s.bounded_path(art["relative_path"])
    if not path.is_file() or s.filehash(path)!=(art["sha256"],art["byte_size"]):
        s.error("LINEAGE_MISMATCH","Project rig-resolution artifact tampered",422)
    doc=json.loads(path.read_bytes())
    if (doc.get("schema_version")!=KIND or doc.get("artifact_id")!=art["artifact_id"]
        or doc.get("project_id")!=art["project_id"] or doc.get("channel_id")!=art["channel_id"]
        or doc.get("revision")!=art["revision"]):
        s.error("LINEAGE_MISMATCH","Project rig-resolution identity mismatch",422)
    return doc


def _context(con,pid):
    pr=a.project(con,pid)
    current=resolver._resolution_in_connection(con,pid)
    actors={entry["requirement"]["requirement_id"]:entry for entry in current["requirements"]
            if entry["requirement"]["kind"]=="actor"}
    return pr,current,actors


def _validate_selected(con,pid,cid,entry,version_id):
    pin=entry["binding"]
    if not pin:
        s.error("RIG_REQUIRED_ACTOR_UNRESOLVED","Required actor has no current approved source pin",422)
    rv=con.execute("SELECT * FROM rig_versions WHERE rig_version_id=? AND channel_id=? AND status='approved'",
                   (version_id,cid)).fetchone()
    if not rv:
        s.error("RIG_VERSION_NOT_APPROVED","Selected rig must be approved and in same channel",422)
    row,meta,docs=rig_proof._candidate_readonly(con,cid,rv["rig_id"],version_id)
    part=docs["parts"]; profile=docs["profile"]; manifest=docs["manifest"]
    if part["asset_version_id"]!=pin["asset_version_id"]:
        s.error("RIG_SOURCE_VERSION_MISMATCH","Actor pin differs from rig source version",422)
    if not set(entry["requirement"]["required_capabilities"]).issubset(set(profile["capabilities"])):
        s.error("RIG_CAPABILITY_UNSUPPORTED","Approved rig does not cover required actor actions",422)
    version=con.execute("SELECT * FROM asset_versions WHERE asset_version_id=? AND channel_id=?",
                       (pin["asset_version_id"],cid)).fetchone()
    if (not version or version["status"]!="approved"
        or version["source_sha256"]!=part["source_image_sha256"]
        or version["visual_style_hash"]!=s.channel_row(con,cid)["visual_style_hash"]):
        s.error("RIG_SOURCE_STALE","Selected approved rig source/style no longer current",422)
    return {"requirement_id":entry["requirement"]["requirement_id"],
            "asset_version_id":pin["asset_version_id"],
            "rig_id":rv["rig_id"],"rig_version_id":version_id,
            "rig_manifest_artifact_id":manifest["artifact_id"],
            "rig_manifest_sha256":con.execute("SELECT sha256 FROM artifacts WHERE artifact_id=?",
                                             (manifest["artifact_id"],)).fetchone()[0],
            "source_image_sha256":part["source_image_sha256"],
            "required_capabilities":entry["requirement"]["required_capabilities"]}


def _evaluate(con,pid,doc):
    pr,current,actors=_context(con,pid)
    if not actors:
        return "blocked",["RIG_ACTOR_REQUIREMENTS_MISSING"]
    if doc is None:
        return "ready",["RIG_REQUIRED_ACTOR_UNRESOLVED"]
    if doc["shot_plan_artifact_id"]!=current["source"]["shot_plan_artifact_id"] or doc["shot_plan_sha256"]!=current["source"]["shot_plan_sha256"] or doc["requirements_fingerprint"]!=current["requirements_fingerprint"]:
        return "stale",["RIG_REQUIREMENTS_CHANGED"]
    selections={v["requirement_id"]:v for v in doc["bindings"]}
    if set(selections)-set(actors):
        return "stale",["RIG_ACTOR_REQUIREMENTS_CHANGED"]
    for reqid,selection in selections.items():
        try:
            fresh=_validate_selected(con,pid,pr["channel_id"],actors[reqid],selection["rig_version_id"])
            if fresh!=selection:
                return "stale",["RIG_SELECTED_VERSION_CHANGED"]
        except (s.DomainError,KeyError,ValueError,OSError):
            return "stale",["RIG_SOURCE_OR_OUTPUT_STALE"]
    if set(selections)!=set(actors):
        return "draft",["RIG_REQUIRED_ACTOR_UNRESOLVED"]
    return "approved",[]


def status(con,pid):
    try:
        pr,current,actors=_context(con,pid)
    except s.DomainError as exc:
        return "blocked",[exc.code]
    art=_latest(con,pid,pr["channel_id"])
    if not art:
        return "ready",["RIG_REQUIRED_ACTOR_UNRESOLVED"] if actors else ("blocked",["RIG_ACTOR_REQUIREMENTS_MISSING"])
    try:
        return _evaluate(con,pid,_document(art))
    except (s.DomainError,KeyError,ValueError,OSError) as exc:
        return "stale",[exc.code if isinstance(exc,s.DomainError) else "RIG_RESOLUTION_INVALID"]


def view(pid):
    with s.reader() as con:
        pr,current,actors=_context(con,pid)
        art=_latest(con,pid,pr["channel_id"])
        doc=_document(art)
        readiness,blockers=_evaluate(con,pid,doc)
        return {"revision":art["revision"] if art else 0,
                "requirements_fingerprint":current["requirements_fingerprint"],
                "actor_requirements":[{"requirement_id":key,
                                       "semantic_key":item["requirement"]["semantic_key"],
                                       "asset_version_id":item["binding"]["asset_version_id"] if item["binding"] else None}
                                      for key,item in actors.items()],
                "bindings":doc["bindings"] if doc else [],
                "readiness":readiness,"blocker_codes":blockers}


def select(pid,requirement_id,rig_version_id,expected_revision):
    with s.reader() as con:
        pr,current,actors=_context(con,pid)
        if requirement_id not in actors:
            s.error("NOT_FOUND","Current actor requirement not found",404)
        old=_latest(con,pid,pr["channel_id"])
        if (old["revision"] if old else 0)!=expected_revision:
            s.error("STALE_HEAD","Rig selection revision changed")
        before=_document(old)
        selected={row["requirement_id"]:row for row in before["bindings"]} if before else {}
        if before and before["requirements_fingerprint"]!=current["requirements_fingerprint"]:
            selected={}
        selected[requirement_id]=_validate_selected(con,pid,pr["channel_id"],actors[requirement_id],rig_version_id)
        # Reject previously selected stale versions; explicit reselection required.
        for reqid in list(selected):
            if reqid not in actors:
                del selected[reqid]
            elif reqid!=requirement_id:
                try:
                    if _validate_selected(con,pid,pr["channel_id"],actors[reqid],selected[reqid]["rig_version_id"])!=selected[reqid]:
                        del selected[reqid]
                except s.DomainError:
                    del selected[reqid]
        aid=s.uid("ar")
        doc={"schema_version":KIND,"artifact_id":aid,"project_id":pid,
             "channel_id":pr["channel_id"],"revision":expected_revision+1,
             "shot_plan_artifact_id":current["source"]["shot_plan_artifact_id"],
             "shot_plan_sha256":current["source"]["shot_plan_sha256"],
             "requirements_fingerprint":current["requirements_fingerprint"],
             "bindings":[selected[key] for key in sorted(selected)],
             "created_at":s.now()}
        cid=pr["channel_id"]
    rel=f"rigs/project-resolutions/{pid}/{aid}.json"
    def commit(con,checksum,size):
        project,fresh,required=_context(con,pid)
        last=_latest(con,pid,cid)
        if (last["revision"] if last else 0)!=expected_revision or fresh["requirements_fingerprint"]!=doc["requirements_fingerprint"]:
            s.error("STALE_HEAD","Rig project selections changed concurrently")
        for item in doc["bindings"]:
            if item["requirement_id"] not in required or _validate_selected(con,pid,cid,required[item["requirement_id"]],item["rig_version_id"])!=item:
                s.error("STALE_HEAD","Actor or selected rig changed during commit")
        approved=set(required)=={x["requirement_id"] for x in doc["bindings"]} and bool(required)
        s.add_artifact(con,aid=aid,channel_id=cid,project_id=pid,kind=KIND,schema=KIND,
            logical=KEY,revision=doc["revision"],status="approved" if approved else "draft",
            checksum=checksum,size=size,relative=rel,metadata={"requirements_fingerprint":doc["requirements_fingerprint"]})
        head=con.execute("SELECT * FROM project_stage_heads WHERE project_id=? AND stage_key='rigging'",(pid,)).fetchone()
        if not head:
            s.error("LINEAGE_MISMATCH","Rigging stage row absent",422)
        con.execute("""UPDATE project_stage_heads SET artifact_id=?,approval_status=?,
            dependency_fingerprint=?,revision=?,updated_at=?
            WHERE project_id=? AND stage_key='rigging' AND revision=?""",
            (aid,"approved" if approved else "draft",
             s.sha({"fingerprint":doc["requirements_fingerprint"],"bindings":doc["bindings"]}),
             head["revision"]+1,s.now(),pid,head["revision"]))
        if con.execute("SELECT changes()").fetchone()[0]!=1:
            s.error("STALE_HEAD","Concurrent rigging head changed")
        return {"artifact_id":aid,"revision":doc["revision"],
                "readiness":"approved" if approved else "draft"}
    return s.document_publish(doc,rel,commit)
