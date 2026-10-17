"""C3 single-user G-Labs durable operations. Provider HTTP contract extracted from YTB.
No HTTP side effects at startup, during prepare or inside SQLite transactions.
"""
from __future__ import annotations
import json
import os
import tempfile
from datetime import datetime,timezone,timedelta
from pathlib import Path
from urllib.parse import urlsplit
from app.animation import service as s, authoring as a, resolver as r, local_assets
from app.animation.provider.glabs_webhook_client import GLabsWebhookClient
from app.animation.provider import AppError

def settings():
    base=os.getenv("GLABS_BASE_URL","http://127.0.0.1:8765").rstrip("/")
    uri=urlsplit(base)
    if uri.scheme not in ("http","https") or uri.hostname not in ("localhost","127.0.0.1") or uri.username or uri.password:
        s.error("VALIDATION_FAILED","G-Labs requires a local service URL",422)
    return {"base_url":base,"api_key":os.getenv("GLABS_API_KEY","")}

def configuration():
    x=settings()
    return {"provider":"glabs_local_webhook","configured":bool(x["api_key"]),
            "base_url":x["base_url"],"live_test":"NOT_RUN_C7"}

def prepare(pid,requirement_id,prompt,negative_prompt,model,aspect_ratio,cost_ceiling_usd):
    if model not in ("nano_banana_2","nano_banana_pro") or aspect_ratio not in ("1:1","3:4","4:3","9:16","16:9"):
        s.error("VALIDATION_FAILED","Unsupported donor model/aspect ratio",422)
    if not isinstance(prompt,str) or not 1<=len(prompt)<=8000 or not isinstance(negative_prompt,str):
        s.error("VALIDATION_FAILED","Invalid prompt",422)
    if type(cost_ceiling_usd) not in (int,float) or not 0<cost_ceiling_usd<=100:
        s.error("CONSENT_INVALID","Explicit cost ceiling in USD required",422)
    state=r.resolution(pid)
    req=next((x["requirement"] for x in state["requirements"] if
              x["requirement"]["requirement_id"]==requirement_id and x["state"]=="unresolved"),None)
    if req is None:s.error("UNAPPROVED_DEPENDENCY","Unresolved requirement required",422)
    opt=settings()
    if not opt["api_key"]:s.error("NOT_READY","GLABS_API_KEY is not configured",503)
    quote={"project_id":pid,"channel_id":r.requirements(pid)["channel_id"],
           "requirement_id":requirement_id,"requirements_fingerprint":state["requirements_fingerprint"],
           "shot_plan_artifact_id":state["source"]["shot_plan_artifact_id"],
           "shot_plan_sha256":state["source"]["shot_plan_sha256"],
           "visual_style_hash":state["source"]["visual_style_hash"],
           "kind":req["kind"],"semantic_key":req["semantic_key"],"view":req["view"],
           "provider":"glabs_local_webhook","base_url":opt["base_url"],
           "payload":{"prompt":prompt,"negative_prompt":negative_prompt,
                     "model":model,"aspect_ratio":aspect_ratio,"upscale":[]},
           "cost_ceiling_usd":float(cost_ceiling_usd),"attempt":1}
    return {"quote":quote,"fingerprint":s.sha(quote),"cost_ceiling_usd":float(cost_ceiling_usd),
            "estimated_cost_usd":None,"explicit_confirmation_required":True}

def status(pid,oid):
    with s.reader() as con:
        a.project(con,pid)
        op=con.execute("SELECT * FROM operations WHERE project_id=? AND operation_id=?",(pid,oid)).fetchone()
        if op is None:s.error("NOT_FOUND","G-Labs operation not found",404)
        item=s.rowdict(op)
        for key in ("request_json","result_json","error_json"):
            item[key[:-5]]=json.loads(item.pop(key)) if item[key] else None
        task=con.execute("SELECT * FROM operation_tasks WHERE operation_id=?",(oid,)).fetchone()
        item["task"]=s.rowdict(task) if task else None
        return item

def confirm(pid,quote,signature,idem,approved):
    if approved is not True or not isinstance(quote,dict) or quote.get("project_id")!=pid:
        s.error("CONSENT_INVALID","Explicit owner approval required",422)
    if signature!=s.sha(quote) or quote.get("attempt")!=1:
        s.error("CONSENT_INVALID","Consent quote identity mismatch",422)
    p=quote.get("payload",{})
    frozen=prepare(pid,quote.get("requirement_id",""),p.get("prompt",""),p.get("negative_prompt",""),
                   p.get("model",""),p.get("aspect_ratio",""),quote.get("cost_ceiling_usd",0))
    if frozen["fingerprint"]!=signature:s.error("STALE_HEAD","Paid consent input changed")
    kh=s.keyhash(idem)
    with s.reader() as con:
        prior=con.execute("""SELECT operation_id,input_fingerprint FROM operations
                         WHERE project_id=? AND kind='glabs_image' AND idempotency_key=?""",(pid,kh)).fetchone()
        if prior:
            if prior["input_fingerprint"]!=signature:s.error("IDEMPOTENCY_CONFLICT","Paid key reused")
            return status(pid,prior["operation_id"])
        rev=con.execute("""SELECT COALESCE(MAX(revision),0)+1 FROM artifacts
                      WHERE project_id=? AND kind='paid_operation_consent.v1'""",(pid,)).fetchone()[0]
    aid,oid,tid,jid=(s.uid(prefix) for prefix in ("ar","op","task","job"))
    expiry=(datetime.now(timezone.utc)+timedelta(minutes=10)).isoformat(timespec="microseconds")
    doc={"schema_version":"paid_operation_consent.v1","artifact_id":aid,"operation_id":oid,
         "project_id":pid,"channel_id":quote["channel_id"],"revision":rev,"created_at":s.now(),
         "input_fingerprint":signature,"cost_ceiling_usd":quote["cost_ceiling_usd"],
         "provider":quote["provider"],"attempt":1,"expires_at":expiry,"quote":quote}
    rel=f"projects/{pid}/generation/consent/{aid}.json"
    def commit(con,digest,size):
        prior=con.execute("SELECT * FROM operations WHERE project_id=? AND kind='glabs_image' AND idempotency_key=?",(pid,kh)).fetchone()
        if prior:
            if prior["input_fingerprint"]!=signature:s.error("IDEMPOTENCY_CONFLICT","Paid key reused")
            return {"operation_id":prior["operation_id"]}
        t=s.now()
        s.add_artifact(con,aid=aid,channel_id=quote["channel_id"],project_id=pid,
            kind="paid_operation_consent.v1",schema="paid_operation_consent.v1",
            logical=oid,revision=rev,status="approved",checksum=digest,size=size,relative=rel,
            metadata={"input_fingerprint":signature,"expires_at":expiry})
        con.execute("""INSERT INTO operations
          (operation_id,project_id,channel_id,kind,status,input_fingerprint,idempotency_key,
           paid_consent_artifact_id,attempt,request_json,created_at,updated_at)
           VALUES (?,?,?,'glabs_image','queued',?,?,?,1,?,?,?)""",
           (oid,pid,quote["channel_id"],signature,kh,aid,s.canon(quote).decode(),t,t))
        con.execute("""INSERT INTO operation_tasks
          (operation_task_id,operation_id,project_id,channel_id,task_key,status,attempt,created_at,updated_at)
          VALUES (?,?,?,?,?,'queued',1,?,?)""",
          (tid,oid,pid,quote["channel_id"],quote["requirement_id"],t,t))
        con.execute("""INSERT INTO jobs
          (job_id,operation_id,project_id,channel_id,kind,status,progress_message,progress_percent,created_at,updated_at)
          VALUES (?,?,?,?,?,'queued','Awaiting explicit submission',0,?,?)""",
          (jid,oid,pid,quote["channel_id"],"glabs_image",t,t))
        return {"operation_id":oid}
    result=s.document_publish(doc,rel,commit)
    return status(pid,result["operation_id"])

def cancel(pid,oid):
    with s.writer() as con:
        a.project(con,pid)
        op=con.execute("SELECT status FROM operations WHERE operation_id=? AND project_id=?",(oid,pid)).fetchone()
        if op is None:s.error("NOT_FOUND","Operation not found",404)
        if op["status"] in ("completed","failed","cancelled"):
            return {"operation_id":oid,"status":op["status"]}
        t=s.now()
        con.execute("UPDATE operations SET status='cancelled',updated_at=? WHERE operation_id=?",(t,oid))
        con.execute("UPDATE operation_tasks SET status='cancelled',updated_at=? WHERE operation_id=?",(t,oid))
        con.execute("UPDATE jobs SET status='cancelled',updated_at=?,progress_message='Cancelled' WHERE operation_id=?",(t,oid))
    return {"operation_id":oid,"status":"cancelled"}

def transition(con,oid,op_status,task_status,handle=None,result=None,err=None):
    t=s.now()
    con.execute("UPDATE operations SET status=?,result_json=?,error_json=?,updated_at=? WHERE operation_id=?",
        (op_status,s.canon(result).decode() if result else None,s.canon(err).decode() if err else None,t,oid))
    con.execute("""UPDATE operation_tasks SET status=?,provider_handle_json=COALESCE(?,provider_handle_json),updated_at=?
                   WHERE operation_id=?""",
        (task_status,s.canon(handle).decode() if handle else None,t,oid))
    con.execute("UPDATE jobs SET status=?,progress_message=?,progress_percent=?,updated_at=? WHERE operation_id=?",
        (op_status,op_status,100 if op_status=="completed" else 50,t,oid))

def advance(pid,oid,client=None):
    with s.writer() as con:
        pr=a.project(con,pid)
        op=con.execute("SELECT * FROM operations WHERE project_id=? AND operation_id=?",(pid,oid)).fetchone()
        if op is None:s.error("NOT_FOUND","Operation not found",404)
        if op["status"] in ("cancelled","completed","failed","unknown"):
            return {"operation_id":oid,"status":op["status"]}
        consent=con.execute("""SELECT * FROM artifacts WHERE artifact_id=? AND project_id=?
                   AND kind='paid_operation_consent.v1' AND approval_status='approved'""",
                   (op["paid_consent_artifact_id"],pid)).fetchone()
        if consent is None:s.error("CONSENT_INVALID","Approved consent missing",422)
        signed=a.verified_doc(consent)
        if signed["input_fingerprint"]!=op["input_fingerprint"] or signed["attempt"]!=op["attempt"] or signed["expires_at"]<s.now():
            s.error("CONSENT_INVALID","Expired or mismatched consent",422)
        quote=json.loads(op["request_json"])
        if r.requirements(pid)["fingerprint"]!=quote["requirements_fingerprint"]:
            s.error("STALE_HEAD","Generation source changed")
        task=con.execute("SELECT * FROM operation_tasks WHERE operation_id=?",(oid,)).fetchone()
        submit=task["status"]=="queued"
        handle=json.loads(task["provider_handle_json"]) if task["provider_handle_json"] else None
        if submit:
            # Durable paid-submit fence before IO. Crash here -> unknown, never blind retry.
            transition(con,oid,"running","submitted")
    if client is None:
        try:client=GLabsWebhookClient(settings())
        except AppError as exc:s.error(exc.code,exc.message,exc.status)
    if submit:
        try:
            reply=client.submit_image(quote["payload"])
            handle={"task_id":reply["task_id"]}
            with s.writer() as con:
                if con.execute("SELECT status FROM operations WHERE operation_id=?",(oid,)).fetchone()["status"]=="cancelled":
                    return status(pid,oid)
                transition(con,oid,"running","running",handle=handle)
        except Exception:
            with s.writer() as con:transition(con,oid,"unknown","unknown",err={"code":"SUBMIT_ACK_UNKNOWN"})
            return status(pid,oid)
    if handle is None:
        with s.writer() as con:transition(con,oid,"unknown","unknown",err={"code":"SUBMIT_ACK_UNKNOWN"})
        return status(pid,oid)
    try:
        remote=client.get_status(handle["task_id"])
        if remote["status"] in ("running","pending"):
            return status(pid,oid)
        if remote["status"]=="failed":
            with s.writer() as con:transition(con,oid,"failed","failed",err={"code":"PROVIDER_FAILED"})
            return status(pid,oid)
        result=client.get_result(handle["task_id"])
        stage=s.artifact_root()
        stage.mkdir(parents=True,exist_ok=True)
        fd,tmp=tempfile.mkstemp(prefix="glabs-",dir=stage)
        os.close(fd)
        try:
            client.download_file(result["results"][0],Path(tmp),local_assets.MAX_BYTES)
            need=r.requirements(pid)
            req=next(x for x in need["requirements"] if x["requirement_id"]==quote["requirement_id"])
            candidate=local_assets.ingest(pid,req["kind"],req["semantic_key"],req["view"],
                Path(tmp).read_bytes(),"glabs-generated.png",origin="glabs",provider_task_id=handle["task_id"])
        finally:Path(tmp).unlink(missing_ok=True)
        with s.writer() as con:
            if con.execute("SELECT status FROM operations WHERE operation_id=?",(oid,)).fetchone()["status"]!="cancelled":
                transition(con,oid,"completed","completed",result={"candidate":candidate,"task_id":handle["task_id"]})
        return status(pid,oid)
    except Exception as exc:
        if isinstance(exc,AppError) and exc.retryable:return status(pid,oid)
        with s.writer() as con:
            if con.execute("SELECT status FROM operations WHERE operation_id=?",(oid,)).fetchone()["status"]!="cancelled":
                transition(con,oid,"failed","failed",err={"code":"RESULT_INVALID_OR_DOWNLOAD_FAILED"})
        return status(pid,oid)
