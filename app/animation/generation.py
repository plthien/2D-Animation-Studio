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
           "provider_identity_hash":s.sha({"endpoint":opt["base_url"],"api_key":opt["api_key"]}),
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
    kh=s.keyhash(idem)
    with s.reader() as con:
        prior=con.execute("SELECT operation_id,input_fingerprint FROM operations WHERE project_id=? AND kind='glabs_image' AND idempotency_key=?",(pid,kh)).fetchone()
        if prior:
            if prior["input_fingerprint"]!=signature:s.error("IDEMPOTENCY_CONFLICT","Paid key reused")
            return status(pid,prior["operation_id"])
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
    """Cancel locally without losing knowledge of a possible paid submission."""
    with s.writer() as con:
        a.project(con,pid)
        op=con.execute("SELECT * FROM operations WHERE operation_id=? AND project_id=?",
                       (oid,pid)).fetchone()
        if op is None:s.error("NOT_FOUND","Operation not found",404)
        if op["status"] in ("completed","failed","cancelled"):
            return {"operation_id":oid,"status":op["status"]}
        task=con.execute("SELECT * FROM operation_tasks WHERE operation_id=?",(oid,)).fetchone()
        if task is None:s.error("LINEAGE_MISMATCH","Operation task missing",422)
        if task["provider_handle_json"]:
            reason="CANCELLED_WITH_PROVIDER_HANDLE"
        elif task["status"] in ("submitted","running","unknown"):
            reason="CANCELLED_SUBMISSION_UNCERTAIN"
        else:
            reason="CANCELLED_BEFORE_SUBMISSION"
        t=s.now()
        updated=con.execute(
            """UPDATE operations SET status='cancelled',error_json=?,lease_owner=NULL,
               lease_token=NULL,lease_expires_at=NULL,updated_at=?
               WHERE operation_id=? AND project_id=? AND status IN ('queued','running','unknown')""",
            (s.canon({"code":reason}).decode(),t,oid,pid),
        )
        if updated.rowcount!=1:s.error("STALE_HEAD","Operation changed during cancel")
        con.execute(
            "UPDATE operation_tasks SET status='cancelled',claim_token=NULL,updated_at=? WHERE operation_id=?",
            (t,oid),
        )
        con.execute(
            """UPDATE jobs SET status='cancelled',updated_at=?,progress_message=? WHERE operation_id=?""",
            (t,reason,oid),
        )
    return {"operation_id":oid,"status":"cancelled"}


def transition(con,oid,op_status,task_status,handle=None,result=None,err=None,
               claim_token=None):
    """CAS transition; terminal cancelled/completed may not be resurrected."""
    t=s.now()
    query="""UPDATE operations SET status=?,result_json=?,error_json=?,updated_at=?,
            lease_owner=CASE WHEN ? THEN NULL ELSE lease_owner END,
            lease_token=CASE WHEN ? THEN NULL ELSE lease_token END,
            lease_expires_at=CASE WHEN ? THEN NULL ELSE lease_expires_at END
            WHERE operation_id=? AND status IN ('queued','running','unknown')"""
    done=op_status in ("completed","failed","unknown")
    args=[op_status,s.canon(result).decode() if result is not None else None,
          s.canon(err).decode() if err is not None else None,t,
          int(done),int(done),int(done),oid]
    if claim_token is not None:
        query+=" AND lease_token=?"
        args.append(claim_token)
    changed=con.execute(query,args)
    if changed.rowcount!=1:return False
    con.execute(
        """UPDATE operation_tasks SET status=?,
           claim_token=CASE WHEN ? THEN NULL ELSE claim_token END,
           provider_handle_json=COALESCE(?,provider_handle_json),updated_at=?
           WHERE operation_id=?""",
        (task_status,int(done),s.canon(handle).decode() if handle else None,t,oid),
    )
    con.execute(
        "UPDATE jobs SET status=?,progress_message=?,progress_percent=?,updated_at=? WHERE operation_id=?",
        (op_status,op_status,100 if op_status=="completed" else 50,t,oid),
    )
    return True


def _claim_advance(con, pid, oid):
    """BEGIN IMMEDIATE owns claim + submit fence; never hold it during provider IO."""
    from uuid import uuid4
    op=con.execute("SELECT * FROM operations WHERE project_id=? AND operation_id=?",
                   (pid,oid)).fetchone()
    if op is None:s.error("NOT_FOUND","Operation not found",404)
    if op["status"] in ("cancelled","completed","failed","unknown"):
        return None
    task=con.execute("SELECT * FROM operation_tasks WHERE operation_id=?",(oid,)).fetchone()
    if task is None:s.error("LINEAGE_MISMATCH","Operation task missing",422)
    instant=s.now()
    if op["lease_token"] and op["lease_expires_at"] and op["lease_expires_at"]>instant:
        return None
    handle=json.loads(task["provider_handle_json"]) if task["provider_handle_json"] else None
    if task["status"] in ("submitted","claimed") and handle is None:
        # Lease expiry/crash after the submit fence is ambiguous, NOT retry permission.
        transition(con,oid,"unknown","unknown",err={"code":"SUBMIT_ACK_UNKNOWN"})
        return None
    submit=task["status"]=="queued"
    if not submit and handle is None:
        transition(con,oid,"unknown","unknown",err={"code":"SUBMIT_ACK_UNKNOWN"})
        return None
    consent=con.execute(
        """SELECT * FROM artifacts WHERE artifact_id=? AND project_id=?
           AND kind='paid_operation_consent.v1' AND approval_status='approved'""",
        (op["paid_consent_artifact_id"],pid),
    ).fetchone()
    if consent is None:s.error("CONSENT_INVALID","Approved consent missing",422)
    signed=a.verified_doc(consent)
    if signed["input_fingerprint"]!=op["input_fingerprint"] or signed["attempt"]!=op["attempt"]:
        s.error("CONSENT_INVALID","Paid consent does not match operation attempt",422)
    quote=json.loads(op["request_json"])
    provider_settings=settings()
    if quote.get("provider_identity_hash")!=s.sha({
            "endpoint":provider_settings["base_url"],"api_key":provider_settings["api_key"]}):
        s.error("CONSENT_INVALID","Provider identity changed since consent",422)
    if r._requirements_in_connection(con,pid)["fingerprint"]!=quote["requirements_fingerprint"]:
        s.error("STALE_HEAD","Generation source changed")
    if submit and signed["expires_at"]<instant:
        s.error("CONSENT_INVALID","Expired paid submission consent",422)
    token=uuid4().hex
    expiry=(datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat(timespec="microseconds")
    changed=con.execute(
        """UPDATE operations SET lease_owner='c3-glabs-advance',lease_token=?,
           lease_expires_at=?,updated_at=?
           WHERE operation_id=? AND project_id=? AND status IN ('queued','running')
             AND (lease_token IS NULL OR lease_expires_at<=?)""",
        (token,expiry,instant,oid,pid,instant),
    )
    if changed.rowcount!=1:return None
    con.execute("UPDATE operation_tasks SET claim_token=?,updated_at=? WHERE operation_id=?",
                (token,instant,oid))
    if submit:
        # Durable paid POST fence. On crash the next advance becomes UNKNOWN, not POST.
        if not transition(con,oid,"running","submitted",claim_token=token):
            s.error("STALE_HEAD","Unable to write paid submit fence")
    return {"token":token,"submit":submit,"handle":handle,"quote":quote,
            "task_id":task["operation_task_id"]}


def _release_claim(pid,oid,token):
    with s.writer() as con:
        t=s.now()
        con.execute(
            """UPDATE operations SET lease_owner=NULL,lease_token=NULL,
               lease_expires_at=NULL,updated_at=?
               WHERE operation_id=? AND project_id=? AND lease_token=?""",
            (t,oid,pid,token),
        )
        con.execute(
            """UPDATE operation_tasks SET claim_token=NULL,updated_at=?
               WHERE operation_id=? AND claim_token=?""",
            (t,oid,token),
        )


def _acknowledge(pid,oid,task_id,token,handle):
    """Always save a real provider task ID, EVEN IF cancellation won the race."""
    with s.writer() as con:
        op=con.execute("SELECT * FROM operations WHERE operation_id=? AND project_id=?",
                       (oid,pid)).fetchone()
        task=con.execute("SELECT * FROM operation_tasks WHERE operation_task_id=? AND operation_id=?",
                         (task_id,oid)).fetchone()
        if op is None or task is None:s.error("LINEAGE_MISMATCH","Provider operation missing",422)
        previous=json.loads(task["provider_handle_json"]) if task["provider_handle_json"] else None
        if previous is not None and previous!=handle:
            s.error("LINEAGE_MISMATCH","Conflicting acknowledged provider task identity",422)
        con.execute(
            """UPDATE operation_tasks SET provider_handle_json=?,updated_at=?
               WHERE operation_task_id=? AND (provider_handle_json IS NULL OR provider_handle_json=?)""",
            (s.canon(handle).decode(),s.now(),task_id,s.canon(handle).decode()),
        )
        if op["status"]=="cancelled":
            con.execute(
                """UPDATE operations SET error_json=?,updated_at=?
                   WHERE operation_id=? AND status='cancelled'""",
                (s.canon({"code":"CANCELLED_WITH_PROVIDER_HANDLE"}).decode(),s.now(),oid),
            )
            return False
        if op["lease_token"]!=token or op["status"]!="running":
            # The handle remains durable for manual reconciliation, no revival.
            return False
        return transition(con,oid,"running","running",handle=handle,claim_token=token)


def _submit_unknown(pid,oid):
    with s.writer() as con:
        op=con.execute("SELECT * FROM operations WHERE operation_id=? AND project_id=?",
                       (oid,pid)).fetchone()
        if op and op["status"]=="running":
            transition(con,oid,"unknown","unknown",err={"code":"SUBMIT_ACK_UNKNOWN"})
        # A cancelled request retains CANCELLED_SUBMISSION_UNCERTAIN and is never retried.


def advance(pid,oid,client=None):
    with s.writer() as con:
        a.project(con,pid)
        claim=_claim_advance(con,pid,oid)
    if claim is None:
        return status(pid,oid)
    token,submit,handle,quote,task_id=(claim[k] for k in
                                      ("token","submit","handle","quote","task_id"))
    try:
        if client is None:
            try:client=GLabsWebhookClient(settings())
            except AppError as exc:
                if submit:_submit_unknown(pid,oid)
                s.error(exc.code,exc.message,exc.status)
        if submit:
            with s.reader() as con:
                current=con.execute("SELECT status,lease_token FROM operations WHERE operation_id=? AND project_id=?",
                                    (oid,pid)).fetchone()
                if not current or current["status"]!="running" or current["lease_token"]!=token:
                    return status(pid,oid)
            try:
                p=quote["payload"]
                provider_prompt=p["prompt"].strip()
                if p["negative_prompt"].strip():
                    provider_prompt+="\n\nAvoid: "+p["negative_prompt"].strip()
                reply=client.submit_image({"prompt":provider_prompt,"model":p["model"],
                     "aspect_ratio":p["aspect_ratio"],"reference_images":[],"upscale":[]})
                handle={"task_id":reply["task_id"]}
                if not _acknowledge(pid,oid,task_id,token,handle):
                    return status(pid,oid)
            except Exception:
                _submit_unknown(pid,oid)
                return status(pid,oid)
        if handle is None:
            _submit_unknown(pid,oid)
            return status(pid,oid)
        with s.reader() as con:
            op=con.execute("SELECT status,lease_token FROM operations WHERE operation_id=? AND project_id=?",
                           (oid,pid)).fetchone()
            if op is None or op["status"]!="running" or op["lease_token"]!=token:
                return status(pid,oid)
        try:
            remote=client.get_status(handle["task_id"])
            if remote["status"] in ("running","pending"):
                return status(pid,oid)
            if remote["status"]=="failed":
                with s.writer() as con:
                    transition(con,oid,"failed","failed",err={"code":"PROVIDER_FAILED"},claim_token=token)
                return status(pid,oid)
            result=client.get_result(handle["task_id"])
            stage=s.artifact_root()
            stage.mkdir(parents=True,exist_ok=True)
            fd,tmp=tempfile.mkstemp(prefix="glabs-",dir=stage)
            os.close(fd)
            try:
                client.download_file(result["results"][0],Path(tmp),local_assets.MAX_BYTES)
                # Pre-ingest cancellation is also checked under local_assets' owning writer.
                with s.reader() as con:
                    need=r._requirements_in_connection(con,pid)
                req=next(x for x in need["requirements"] if x["requirement_id"]==quote["requirement_id"])
                candidate=local_assets.ingest(
                    pid,req["kind"],req["semantic_key"],req["view"],Path(tmp).read_bytes(),
                    "glabs-generated.png",origin="glabs",provider_task_id=handle["task_id"],
                    operation_id=oid,operation_task_id=task_id,claim_token=token,result_index=0,
                )
            finally:
                Path(tmp).unlink(missing_ok=True)
            with s.writer() as con:
                transition(con,oid,"completed","completed",claim_token=token,
                           result={"candidate":candidate,"task_id":handle["task_id"]})
            return status(pid,oid)
        except Exception as exc:
            if isinstance(exc,s.DomainError) and exc.code=="STALE_HEAD":
                return status(pid,oid)
            if isinstance(exc,AppError) and exc.retryable:
                return status(pid,oid)
            with s.writer() as con:
                transition(con,oid,"failed","failed",claim_token=token,
                           err={"code":"RESULT_INVALID_OR_DOWNLOAD_FAILED"})
            return status(pid,oid)
    finally:
        _release_claim(pid,oid,token)


def list_operations(pid):
    with s.reader() as con:
        a.project(con,pid)
        rows=con.execute("""SELECT operation_id,status,input_fingerprint,created_at,updated_at
                            FROM operations WHERE project_id=? AND kind='glabs_image'
                            ORDER BY created_at DESC LIMIT 50""",(pid,)).fetchall()
        return {"items":[s.rowdict(x) for x in rows],"next_cursor":None}


def reconcile_unknown(pid,oid,provider_task_id,confirmed_owner_match,client=None):
    """Manual safe reconciliation by a real provider handle, never another paid POST."""
    if confirmed_owner_match is not True:
        s.error("CONSENT_INVALID","Owner must confirm this provider task belongs to the frozen attempt",422)
    canonical=GLabsWebhookClient.normalize_task_id(provider_task_id)
    with s.reader() as con:
        a.project(con,pid)
        op=con.execute("SELECT * FROM operations WHERE operation_id=? AND project_id=?",(oid,pid)).fetchone()
        if op is None:s.error("NOT_FOUND","Operation not found",404)
        if op["status"]!="unknown":s.error("STALE_HEAD","Only unknown submissions may be reconciled")
        quote=json.loads(op["request_json"])
    if r.requirements(pid)["fingerprint"]!=quote["requirements_fingerprint"]:
        s.error("STALE_HEAD","Cannot reconcile under changed source fingerprint")
    if client is None:client=GLabsWebhookClient(settings())
    try:
        remote=client.get_status(canonical)  # GET only, not a second paid submit.
    except AppError as exc:
        s.error(exc.code,exc.message,exc.status)
    with s.writer() as con:
        current=con.execute("SELECT status FROM operations WHERE operation_id=? AND project_id=?",(oid,pid)).fetchone()
        if current is None or current["status"]!="unknown":
            s.error("STALE_HEAD","Operation changed during provider reconciliation")
        transition(con,oid,"running","running",handle={"task_id":canonical})
    return advance(pid,oid,client=client)
