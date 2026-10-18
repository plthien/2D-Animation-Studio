"""C5 Director source-bound external authoring and conservative motion capability validation."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from app.animation import service as s, authoring as a, rig_resolution, rig_proof, resolver

KIND="animation_plan.v1"
SCHEMA=json.loads((Path(__file__).resolve().parents[2]/"contracts/animation/schemas/animation_plan.v1.schema.json").read_text(encoding="utf-8"))
CHECK=Draft202012Validator(SCHEMA,format_checker=FormatChecker())
ACTIONS=frozenset(("idle","walk_to","look_at","reach_for","grab","carry_to","place_at","point_at","react"))
CHANNELS={"idle":set(),"walk_to":{"root","legs"},"look_at":{"head"},
 "reach_for":{"hand"},"grab":{"hand","prop"},"carry_to":{"root","legs","hand","prop"},
 "place_at":{"hand","prop"},"point_at":{"hand"},"react":{"chest","head"}}
TARGETS={"idle":"none","walk_to":"anchor","look_at":"spatial","reach_for":"prop",
 "grab":"prop","carry_to":"anchor","place_at":"anchor","point_at":"spatial","react":"optional"}

def _artifact_doc(row):
    return a.verified_doc(row)

def _context(con,pid):
    project=a.project(con,pid)
    channel=s.channel_row(con,project["channel_id"])
    shot=resolver.current_shot(con,pid)
    rstate,rblock=rig_resolution.status(con,pid)
    if rstate!="approved":
        s.error("UNAPPROVED_DEPENDENCY","Approved current project rig selections required",422,blockers=rblock)
    rig_art=rig_resolution._latest(con,pid,project["channel_id"])
    if rig_art is None or rig_art["approval_status"]!="approved":
        s.error("UNAPPROVED_DEPENDENCY","Current approved rig selection artifact required",422)
    rig_doc=rig_resolution._document(rig_art)
    req=resolver._resolution_in_connection(con,pid)
    required={e["requirement"]["requirement_id"]:e for e in req["requirements"]
              if e["requirement"]["kind"]=="actor"}
    chosen={x["requirement_id"]:x for x in rig_doc["bindings"]}
    if not required or required.keys()!=chosen.keys():
        s.error("UNAPPROVED_DEPENDENCY","All actor rigs must be selected",422)
    rigs={}
    for reqid,entry in required.items():
        selected=chosen[reqid]
        valid=rig_resolution._validate_selected(con,pid,project["channel_id"],entry,selected["rig_version_id"])
        if valid!=selected:s.error("STALE_HEAD","Actor rig selection changed")
        rv=con.execute("SELECT * FROM rig_versions WHERE rig_version_id=? AND channel_id=?",
                       (selected["rig_version_id"],project["channel_id"])).fetchone()
        meta=con.execute("SELECT * FROM artifacts WHERE artifact_id=?",
                         (rv["rig_manifest_artifact_id"],)).fetchone()
        _,_,docs=rig_proof._candidate_readonly(con,project["channel_id"],rv["rig_id"],rv["rig_version_id"])
        # Capabilities claimed by the immutable C4 profile are the baseline; no automatic nine-action promotion.
        rigs[entry["requirement"]["semantic_key"]]={
            "requirement_id":reqid,"rig_id":rv["rig_id"],"rig_version_id":rv["rig_version_id"],
            "rig_profile_artifact_id":rv["rig_profile_artifact_id"],
            "rig_manifest_artifact_id":meta["artifact_id"],"rig_manifest_sha256":meta["sha256"],
            "capabilities":sorted(docs["profile"]["capabilities"]),
            "bones":docs["profile"]["bones"]}
    source={"shot_plan_artifact_id":shot["artifact_id"],"shot_plan_sha256":shot["sha256"],
            "rig_resolution_artifact_id":rig_art["artifact_id"],"rig_resolution_sha256":rig_art["sha256"],
            "performance_style_hash":channel["performance_style_hash"],
            "rigs":rigs}
    return project,channel,shot,rig_art,source,s.sha(source)

def _revision(con,pid):
    return con.execute("SELECT COALESCE(MAX(revision),0)+1 FROM artifacts WHERE project_id=? AND kind=?",
                       (pid,KIND)).fetchone()[0]

def prompt(pid):
    with s.writer() as con:
        project,channel,shot,rig_art,source,fingerprint=_context(con,pid)
        aid=s.uid("ar");rid=s.uid("rs");revision=_revision(con,pid);now=s.now()
        expires=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat(timespec="microseconds")
        con.execute("""INSERT INTO authoring_reservations
          (reservation_id,project_id,channel_id,kind,schema_version,source_head_artifact_id,
           source_fingerprint,reserved_artifact_id,status,expires_at,consumed_artifact_id,created_at,updated_at)
           VALUES (?,?,?,?,?,?,?,?, 'open',?,NULL,?,?)""",
           (rid,pid,project["channel_id"],KIND,KIND,shot["artifact_id"],fingerprint,aid,expires,now,now))
        dna=con.execute("SELECT * FROM artifacts WHERE artifact_id=?",
                        (channel["current_dna_artifact_id"],)).fetchone()
        rig_doc=rig_resolution._document(rig_art)
        shot_doc=_artifact_doc(shot)
        dna_doc=_artifact_doc(dna)
    fields={"schema_version":KIND,"artifact_id":aid,"channel_id":project["channel_id"],
            "project_id":pid,"revision":revision,"created_at":now,
            "shot_plan_artifact_id":shot["artifact_id"],
            "rig_profile_artifact_ids":sorted({r["rig_profile_artifact_id"] for r in source["rigs"].values()})}
    package={"reservation_id":rid,"source_fingerprint":fingerprint,"reserved_fields":fields,
             "source_inputs":source,"shot_plan":shot_doc,"rig_resolution":rig_doc,
             "channel_dna_performance":dna_doc.get("performance"),"schema":SCHEMA}
    guidance=("Return ONLY animation_plan.v1 JSON matching the complete schema and reserved_fields EXACTLY. "
       "Do not invent backend-owned hashes, artifact IDs, shot IDs, actor IDs or prop IDs. "
       "All intervals are integer half-open [start_frame,end_frame) within shot duration, 24fps. "
       "Supported actions: idle, walk_to, look_at, reach_for, grab, carry_to, place_at, point_at, react. "
       "Spatial targets must exist in frozen shot spatial_anchors; prop targets must exist in shot prop_ids. "
       "Use hand left/right for hand actions and none otherwise. Each hand may control one prop, no duplicate prop owners. "
       "C4 rig capability constraints are authoritative: unsupported actions will be rejected until an explicitly "
       "verified immutable C5 capability certification is approved. No hidden in-app LLM call.")
    return {"reservation_id":rid,"reserved_artifact_id":aid,"revision":revision,
        "source_fingerprint":fingerprint,"expires_at":expires,"reserved_fields":fields,
        "schema":SCHEMA,"prompt_text":guidance+"\n\n=== BEGIN DIRECTOR PACKAGE JSON ===\n"+
             json.dumps(package,ensure_ascii=False,sort_keys=True,indent=2)+"\n=== END DIRECTOR PACKAGE JSON ===",
        "source":source}

def _issues(con,pid,doc,ctx):
    project,channel,shot,rig_art,source,fingerprint=ctx
    issues=[]
    def issue(path,message):issues.append({"path":path,"message":message})
    fields={"schema_version":KIND,"channel_id":project["channel_id"],"project_id":pid,
            "shot_plan_artifact_id":shot["artifact_id"],
            "rig_profile_artifact_ids":sorted({r["rig_profile_artifact_id"] for r in source["rigs"].values()})}
    for k,v in fields.items():
        if doc.get(k)!=v:issue(k,"Wrong current approved source or identity")
    shots={r["shot_id"]:r for r in _artifact_doc(shot)["shots"]}
    ids=set()
    controls={}
    for index,item in enumerate(doc.get("actions",[])):
        path=f"actions/{index}"
        if not isinstance(item,dict):continue
        ident=item.get("action_id")
        if ident in ids:issue(path+"/action_id","Duplicate action identity")
        ids.add(ident)
        sh=shots.get(item.get("shot_id"))
        if sh is None:issue(path+"/shot_id","Unknown shot");continue
        actor=item.get("actor_id")
        if actor not in sh["actor_ids"]:issue(path+"/actor_id","Actor absent from shot");continue
        typ=item.get("action")
        start,end=item.get("start_frame"),item.get("end_frame")
        if type(start)!=int or type(end)!=int or start<0 or start>=end or end>sh["duration_frames"]:
            issue(path+"/start_frame","Action must be inside shot's integer half-open interval");continue
        hand=item.get("hand")
        prop=item.get("prop_id")
        target=item.get("target_id")
        anchor={a["anchor_id"] for a in sh["spatial_anchors"]}
        known_prop=set(sh["prop_ids"])
        required=TARGETS.get(typ)
        if required=="anchor" and target not in anchor:issue(path+"/target_id","Unknown spatial anchor")
        if required in ("prop","spatial") and target not in anchor|known_prop|set(sh["actor_ids"]):
            issue(path+"/target_id","Unknown spatial reference")
        if required=="none" and (target is not None or prop is not None):
            issue(path,"Idle cannot have target/prop")
        if typ in ("reach_for","grab") and (prop not in known_prop or target!=prop):
            issue(path+"/prop_id","Reach/grab requires existing targeted prop")
        if typ in ("carry_to","place_at") and prop not in known_prop:
            issue(path+"/prop_id","Carry/place requires real prop")
        if typ in ("reach_for","grab","carry_to","place_at","point_at") and hand not in ("left","right"):
            issue(path+"/hand","Action requires an explicit left/right hand")
        if typ in ("walk_to","look_at","react","idle") and hand!="none":
            issue(path+"/hand","Hand must be none for this action")
        rig=source["rigs"].get(actor)
        if rig is None:issue(path+"/actor_id","No approved rig for actor");continue
        if typ not in rig["capabilities"]:
            issue(path+"/action","RIG_CAPABILITY_UNSUPPORTED: "+str(typ))
        channels=CHANNELS.get(typ,set())
        for channel_name in set(hand if control == "hand" else "prop:"+str(prop) if control == "prop" else control for control in channels):
            key=(sh["shot_id"],actor,channel_name)
            for old_start,old_end,old_id in controls.get(key,[]):
                if start<old_end and old_start<end:
                    issue(path,"Conflicting "+channel_name+" action overlaps "+str(old_id))
            controls.setdefault(key,[]).append((start,end,ident))
    return issues

def validate(pid,reservation_id,document):
    if not isinstance(document,dict):s.error("VALIDATION_FAILED","Expected JSON object",422)
    with s.reader() as con:
        ctx=_context(con,pid)
        reservation=con.execute("SELECT * FROM authoring_reservations WHERE reservation_id=? AND project_id=? AND kind=?",
                                (reservation_id,pid,KIND)).fetchone()
        if not reservation:s.error("NOT_FOUND","Director reservation not found",404)
        if reservation["status"]!="open" or reservation["expires_at"]<s.now():
            s.error("STALE_HEAD","Director reservation consumed/expired")
        if reservation["source_fingerprint"]!=ctx[-1]:
            s.error("STALE_HEAD","Shot/rig/performance source changed")
        issues=[{"path":"/".join(map(str,e.absolute_path)),"message":e.message} for e in CHECK.iter_errors(document)]
        if not issues:
            for k,v in {"artifact_id":reservation["reserved_artifact_id"],
                        "revision":_revision(con,pid)}.items():
                if document.get(k)!=v:issues.append({"path":k,"message":"Reserved immutable identity mismatch"})
            issues.extend(_issues(con,pid,document,ctx))
        return {"valid":not issues,"issues":issues,"source_fingerprint":ctx[-1]}

def import_draft(pid,reservation_id,document):
    report=validate(pid,reservation_id,document)
    if not report["valid"]:s.error("VALIDATION_FAILED","Director plan rejected",422,issues=report["issues"])
    aid=document["artifact_id"];rel=f"projects/{pid}/director/{aid}.json"
    def commit(con,digest,size):
        ctx=_context(con,pid)
        reservation=con.execute("SELECT * FROM authoring_reservations WHERE reservation_id=? AND project_id=? AND kind=?",
                                (reservation_id,pid,KIND)).fetchone()
        if (reservation is None or reservation["status"]!="open"
            or reservation["source_fingerprint"]!=ctx[-1] or ctx[-1]!=report["source_fingerprint"]
            or reservation["reserved_artifact_id"]!=aid or _revision(con,pid)!=document["revision"]):
            s.error("STALE_HEAD","Director source or reservation changed during import")
        issues=_issues(con,pid,document,ctx)
        if issues:s.error("VALIDATION_FAILED","Director inputs changed",422,issues=issues)
        s.add_artifact(con,aid=aid,channel_id=ctx[0]["channel_id"],project_id=pid,
                       kind=KIND,schema=KIND,logical=KIND,revision=document["revision"],
                       status="draft",checksum=digest,size=size,relative=rel,
                       metadata={"reservation_id":reservation_id,"source_fingerprint":ctx[-1]})
        con.execute("UPDATE authoring_reservations SET status='consumed',consumed_artifact_id=?,updated_at=? WHERE reservation_id=? AND status='open'",
                    (aid,s.now(),reservation_id))
        return s.artifact_view(con.execute("SELECT * FROM artifacts WHERE artifact_id=?",(aid,)).fetchone())
    return s.document_publish(document,rel,commit)

def approve(pid,aid,expected_head_revision,expected_sha256):
    with s.writer() as con:
        ctx=_context(con,pid)
        row=con.execute("SELECT * FROM artifacts WHERE project_id=? AND artifact_id=? AND kind=?",
                        (pid,aid,KIND)).fetchone()
        if not row:s.error("NOT_FOUND","Director draft missing",404)
        if row["sha256"]!=expected_sha256:s.error("LINEAGE_MISMATCH","Director draft SHA mismatch",422)
        doc=_artifact_doc(row)
        issues=_issues(con,pid,doc,ctx)
        if issues:s.error("VALIDATION_FAILED","Director plan no longer valid",422,issues=issues)
        if json.loads(row["metadata_json"])["source_fingerprint"]!=ctx[-1]:
            s.error("STALE_HEAD","Director source changed")
        if row["approval_status"]!="draft":s.error("STALE_HEAD","Director already reviewed")
        head=con.execute("SELECT * FROM project_stage_heads WHERE project_id=? AND stage_key='director'",(pid,)).fetchone()
        if not head or head["revision"]!=expected_head_revision:s.error("STALE_HEAD","Director head revision changed")
        con.execute("UPDATE artifacts SET approval_status='approved',reviewed_by='local-user',reviewed_at=? WHERE artifact_id=?",(s.now(),aid))
        changed=con.execute("""UPDATE project_stage_heads
                 SET artifact_id=?,approval_status='approved',dependency_fingerprint=?,revision=revision+1,updated_at=?
                 WHERE project_id=? AND stage_key='director' AND revision=?""",
                 (aid,ctx[-1],s.now(),pid,expected_head_revision))
        if changed.rowcount!=1:s.error("STALE_HEAD","Concurrent Director approval")
        return {"artifact_id":aid,"sha256":row["sha256"],"revision":expected_head_revision+1}

def history(pid):
    with s.reader() as con:
        a.project(con,pid)
        rows=con.execute("SELECT * FROM artifacts WHERE project_id=? AND kind=? ORDER BY revision DESC LIMIT 50",(pid,KIND)).fetchall()
        return {"items":[s.artifact_view(x) for x in rows]}

def read(pid,aid):
    with s.reader() as con:
        a.project(con,pid)
        row=con.execute("SELECT * FROM artifacts WHERE project_id=? AND artifact_id=? AND kind=?",(pid,aid,KIND)).fetchone()
        if not row:s.error("NOT_FOUND","Director artifact missing",404)
        return {"artifact":s.artifact_view(row),"document":_artifact_doc(row)}
