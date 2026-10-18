"""Immutable C5 motion compilation and per-frame deterministic API."""
from __future__ import annotations
import json
from pathlib import Path
from app.animation import service as s, authoring as a, director, motion, motion_world

KIND="compiled_film.v1"
SCHEMA=json.loads((Path(__file__).resolve().parents[2]/"contracts/animation/schemas/compiled_film.v1.schema.json").read_text(encoding="utf-8"))
ENGINE_VERSION="c5-motion-evaluator.v1"

def _approved(con,pid):
    ctx=director._context(con,pid)
    row=con.execute("""SELECT * FROM artifacts WHERE project_id=? AND kind='animation_plan.v1'
               AND approval_status='approved' ORDER BY revision DESC LIMIT 1""",(pid,)).fetchone()
    if row is None:s.error("UNAPPROVED_DEPENDENCY","Approve a current AnimationPlan before compiling",422)
    if json.loads(row["metadata_json"])["source_fingerprint"]!=ctx[-1]:
        s.error("STALE_HEAD","AnimationPlan source/rig/performance changed")
    plan=a.verified_doc(row)
    issues=director._issues(con,pid,plan,ctx)
    if issues:s.error("VALIDATION_FAILED","Approved AnimationPlan no longer executable",422,issues=issues)
    return ctx,row,plan

def _source(ctx,row):
    return {"animation_plan_id":row["artifact_id"],"animation_plan_sha":row["sha256"],
            "director_source":ctx[-1],"engine":ENGINE_VERSION}

def _current(con,pid,aid=None):
    if aid:
        row=con.execute("SELECT * FROM artifacts WHERE artifact_id=? AND project_id=? AND kind=?",
                        (aid,pid,KIND)).fetchone()
    else:
        row=con.execute("SELECT * FROM artifacts WHERE project_id=? AND kind=? ORDER BY revision DESC LIMIT 1",
                        (pid,KIND)).fetchone()
    if row is None:s.error("NOT_FOUND","Compiled film unavailable",404)
    doc=a.verified_doc(row)
    return row,doc

def compile(pid):
    with s.reader() as con:
        ctx,approved,plan=_approved(con,pid)
        inputs=_source(ctx,approved)
        input_fp=s.sha(inputs)
        prior=con.execute("""SELECT * FROM artifacts WHERE project_id=? AND kind=?
              AND json_extract(metadata_json,'$.input_fingerprint')=? AND approval_status='approved'""",
              (pid,KIND,input_fp)).fetchone()
        if prior is not None:
            result=_activate(con,pid,prior,input_fp) # read-only reuse if head already active
            if result is not None:return result
        duration={x["shot_id"]:x for x in a.verified_doc(ctx[2])["shots"]}
        bones=motion.rig_bones_by_actor(con,ctx[-2])
        revision=con.execute("SELECT COALESCE(MAX(revision),0)+1 FROM artifacts WHERE project_id=? AND kind=?",
                             (pid,KIND)).fetchone()[0]
    shots=[];start=0
    # Full-frame checks use immutable plan and actual skeleton geometry; reject failures.
    for sid,shot in duration.items():
        motion_world.verify_choreography(shot,plan,bones)
        hashes=[]
        for frame in range(shot["duration_frames"]):
            state=motion.evaluate(shot,plan,bones,frame)
            hashes.append(s.sha(state))
        shots.append({"shot_id":sid,"global_start_frame":start,
                      "frame_count":shot["duration_frames"],
                      "world_state_sha256":s.sha(hashes),
                      "action_ids":[act["action_id"] for act in plan["actions"] if act["shot_id"]==sid]})
        start+=shot["duration_frames"]
    aid=s.uid("ar");timestamp=s.now()
    doc={"schema_version":KIND,"artifact_id":aid,"channel_id":ctx[0]["channel_id"],
         "project_id":pid,"revision":revision,"created_at":timestamp,
         "animation_plan_artifact_id":approved["artifact_id"],
         "shot_plan_artifact_id":ctx[2]["artifact_id"],
         "input_fingerprint":input_fp,"shots":shots}
    sidecar={"schema_version":ENGINE_VERSION,"shot_plan_sha":ctx[2]["sha256"],
             "animation_plan_sha":approved["sha256"],"source":inputs,
             "shots":[{"shot_id":row["shot_id"],"world_state_sha256":row["world_state_sha256"]}
                      for row in shots]}
    rel=f"projects/{pid}/motion/{aid}.json"
    def commit(con,digest,size):
        fresh,art,_=_approved(con,pid)
        if s.sha(_source(fresh,art))!=input_fp:
            s.error("STALE_HEAD","Source/rig/plan changed during motion compile")
        old=con.execute("""SELECT * FROM artifacts WHERE project_id=? AND kind=?
            AND json_extract(metadata_json,'$.input_fingerprint')=? AND approval_status='approved'""",
            (pid,KIND,input_fp)).fetchone()
        if old is not None:
            return _activate_write(con,pid,old,input_fp)
        next_rev=con.execute("SELECT COALESCE(MAX(revision),0)+1 FROM artifacts WHERE project_id=? AND kind=?",
                             (pid,KIND)).fetchone()[0]
        if revision!=next_rev:s.error("STALE_HEAD","Concurrent motion revision changed")
        s.add_artifact(con,aid=aid,channel_id=ctx[0]["channel_id"],project_id=pid,kind=KIND,
             schema=KIND,logical="motion",revision=revision,status="approved",
             checksum=digest,size=size,relative=rel,
             metadata={"input_fingerprint":input_fp,"evaluator_version":ENGINE_VERSION,
                       "evaluation_sha256":s.sha(sidecar)})
        con.execute("UPDATE artifacts SET parents_json=?,source_fingerprints_json=? WHERE artifact_id=?",
            (s.canon([approved["artifact_id"],ctx[2]["artifact_id"]]).decode(),
             s.canon(inputs).decode(),aid))
        return _activate_write(con,pid,con.execute("SELECT * FROM artifacts WHERE artifact_id=?",(aid,)).fetchone(),input_fp,pending_doc=doc)
    return s.document_publish(doc,rel,commit)

def _activate(con,pid,record,key):
    head=con.execute("SELECT * FROM project_stage_heads WHERE project_id=? AND stage_key='motion'",(pid,)).fetchone()
    if head and head["artifact_id"]==record["artifact_id"] and head["dependency_fingerprint"]==key:
        return s.artifact_view(record)
    return None

def _activate_write(con,pid,row,key,pending_doc=None):
    ctx,art,_=_approved(con,pid)
    if s.sha(_source(ctx,art))!=key or json.loads(row["metadata_json"])["input_fingerprint"]!=key:
        s.error("STALE_HEAD","Compiled film source mismatch")
    doc=pending_doc or a.verified_doc(row)
    if (doc["animation_plan_artifact_id"]!=art["artifact_id"]
            or doc["shot_plan_artifact_id"]!=ctx[2]["artifact_id"]
            or doc["input_fingerprint"]!=key):
        s.error("LINEAGE_MISMATCH","Compiled film document stale",422)
    head=con.execute("SELECT * FROM project_stage_heads WHERE project_id=? AND stage_key='motion'",(pid,)).fetchone()
    if head is None:s.error("LINEAGE_MISMATCH","Motion head missing",422)
    if head["artifact_id"]!=row["artifact_id"] or head["dependency_fingerprint"]!=key:
        updated=con.execute("""UPDATE project_stage_heads SET artifact_id=?,approval_status='approved',
             dependency_fingerprint=?,revision=revision+1,updated_at=?
             WHERE project_id=? AND stage_key='motion' AND revision=?""",
             (row["artifact_id"],key,s.now(),pid,head["revision"]))
        if updated.rowcount!=1:s.error("STALE_HEAD","Motion head update conflict")
    return s.artifact_view(row)

def read(pid,aid):
    with s.reader() as con:
        ctx,art,plan=_approved(con,pid)
        row,doc=_current(con,pid,aid)
        if doc["input_fingerprint"]!=s.sha(_source(ctx,art)):
            s.error("STALE_HEAD","Compilation is stale")
        return {"artifact":s.artifact_view(row),"document":doc}

def frame(pid,aid,shot_id,frame_index):
    with s.reader() as con:
        ctx,art,plan=_approved(con,pid)
        row,doc=_current(con,pid,aid)
        if doc["input_fingerprint"]!=s.sha(_source(ctx,art)):
            s.error("STALE_HEAD","Compiled inputs have changed")
        if not any(x["shot_id"]==shot_id for x in doc["shots"]):
            s.error("NOT_FOUND","Shot not found in compilation",404)
        shots={x["shot_id"]:x for x in a.verified_doc(ctx[2])["shots"]}
        bones=motion.rig_bones_by_actor(con,ctx[-2])
        shot=shots.get(shot_id)
        if shot is None:s.error("STALE_HEAD","Shot source no longer exists")
        value=motion.evaluate(shot,plan,bones,frame_index)
        value["rigs"]={actor:{"rig_id":rig["rig_id"],"rig_version_id":rig["rig_version_id"]}
                       for actor,rig in ctx[-2]["rigs"].items()}
        value["fingerprint"]=s.sha(value)
        return value

def status(pid):
    with s.reader() as con:
        try:
            ctx,art,plan=_approved(con,pid)
        except s.DomainError as exc:return {"readiness":"blocked","blockers":[exc.code]}
        key=s.sha(_source(ctx,art))
        row=con.execute("SELECT * FROM artifacts WHERE project_id=? AND kind=? AND approval_status='approved' ORDER BY revision DESC LIMIT 1",
                        (pid,KIND)).fetchone()
        if row is None:return {"readiness":"ready","blockers":[]}
        try:a.verified_doc(row)
        except s.DomainError as exc:return {"readiness":"stale","blockers":[exc.code]}
        if json.loads(row["metadata_json"]).get("input_fingerprint")!=key:
            return {"readiness":"stale","blockers":["MOTION_SOURCE_CHANGED"]}
        return {"readiness":"approved","blockers":[],"artifact_id":row["artifact_id"]}
