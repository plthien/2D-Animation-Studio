"""Only supported 2D Animation Studio API. No legacy routes or workers."""
from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager
from typing import Any, Annotated

from fastapi import FastAPI, Header, Query, Request, UploadFile, File, Form
from fastapi.routing import APIRoute
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, ConfigDict, Field

from app.animation import service as svc
from app.animation import authoring as auth
from app.animation import resolver as assets
from app.animation import local_assets as localimages
from app.animation import generation as glabs
from app.animation.provider import AppError as ProviderAppError
from app.animation.strict_json import parse_strict_document
from app.animation.database import LegacyDatabaseUnsupported, migrate


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.ready = False
    app.state.startup_error = None
    try:
        if os.environ.get("AUTO_APPLY_MIGRATIONS", "true").lower() in ("true", "1", "yes"):
            migrate()
        else:
            # Schema readiness must still be proven rather than assumed.
            from app.animation.database import guard_database, connect, APPLICATION_TABLES
            from pathlib import Path
            import sqlite3
            db_path = guard_database()
            if not db_path.is_file():
                raise RuntimeError("NOT_READY: animation database not initialized")
            with connect() as conn:
                actual = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
                if actual != APPLICATION_TABLES | {"alembic_version"}:
                    raise RuntimeError("NOT_READY: animation schema differs from frozen contract")
        app.state.ready = True
    except LegacyDatabaseUnsupported as exc:
        app.state.startup_error = str(exc)
        raise
    yield


MAX_C2_JSON_BYTES = 1_048_576


class StrictC2JSONRoute(APIRoute):
    """Validate bytes before FastAPI's Pydantic body parsing on every write route.

    The exact parsed object is cached as Request._json; FastAPI then consumes
    that same document. Neither permissive double parsing nor body truncation
    can turn an invalid request into a DB write.
    """

    def get_route_handler(self):
        handler = super().get_route_handler()

        async def validated(request: Request):
            if request.url.path.endswith("/images/import") and request.method=="POST":
                return await handler(request)
            if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
                media = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                if media != "application/json":
                    svc.error("VALIDATION_FAILED", "Request validation failed", 422)
                declared = request.headers.get("content-length")
                if declared:
                    try:
                        if int(declared) > MAX_C2_JSON_BYTES:
                            svc.error("VALIDATION_FAILED", "Request validation failed", 422)
                    except ValueError:
                        svc.error("VALIDATION_FAILED", "Request validation failed", 422)
                chunks = []
                length = 0
                async for piece in request.stream():
                    length += len(piece)
                    if length > MAX_C2_JSON_BYTES:
                        svc.error("VALIDATION_FAILED", "Request validation failed", 422)
                    chunks.append(piece)
                body = b"".join(chunks)
                try:
                    document = parse_strict_document(body.decode("utf-8", errors="strict"),
                                                     max_bytes=MAX_C2_JSON_BYTES)
                except UnicodeError:
                    svc.error("VALIDATION_FAILED", "Request validation failed", 422)
                request._body = body
                request._json = document
            return await handler(request)

        return validated


app = FastAPI(title="2D Animation Studio", version="0.2.0-c2", lifespan=lifespan)
app.router.route_class = StrictC2JSONRoute
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Idempotency-Key"],
)

ALLOWED_HOSTS = {"127.0.0.1", "localhost", "testserver"}
ALLOWED_ORIGINS = {"http://127.0.0.1:5173", "http://localhost:5173"}


def request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "req_unknown")


def enveloped(request: Request, data: Any, status: int = 200) -> JSONResponse:
    return JSONResponse(
        {"data": data, "meta": {"request_id": request_id(request), "schema_version": "api.v1"}},
        status_code=status,
    )


def err_json(request: Request, code: str, message: str,
             status: int, details: Any | None = None) -> JSONResponse:
    return JSONResponse(
        {"error": {"code": code, "message": message, "details": details or {},
                   "request_id": request_id(request)}},
        status_code=status,
    )


@app.middleware("http")
async def local_only(request: Request, next_handler):
    request.state.request_id = "req_" + uuid.uuid4().hex
    ip = request.client.host if request.client else ""
    hostname = request.headers.get("host", "").split(":")[0].lower()
    origin = request.headers.get("origin")
    if ip not in ("127.0.0.1", "::1", "testclient") or hostname not in ALLOWED_HOSTS:
        return err_json(request, "LOCAL_ONLY", "This service accepts loopback requests only", 403)
    if origin is not None and origin not in ALLOWED_ORIGINS:
        return err_json(request, "ORIGIN_REJECTED", "Origin not allowed", 403)
    return await next_handler(request)


@app.exception_handler(ProviderAppError)
async def provider_error(request: Request, exc: ProviderAppError):
    return err_json(request, exc.code, exc.message, exc.status, exc.details)


@app.exception_handler(svc.DomainError)
async def domain_error(request: Request, exc: svc.DomainError):
    return err_json(request, exc.code, exc.message, exc.status, exc.details)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    return err_json(request, "VALIDATION_FAILED", "Request validation failed", 422,
                    {"issues": [{"path": "/".join(map(str, problem.get("loc", []))),
                                 "message": str(problem.get("msg", ""))} for problem in exc.errors()]})


class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ChannelCreate(Payload):
    name: str
    slug: str


class ChannelUpdate(Payload):
    expected_updated_at: str
    name: str | None = None
    slug: str | None = None


class Archive(Payload):
    expected_updated_at: str


class ProjectCreate(Payload):
    channel_id: str
    name: str
    slug: str


class DnaRevision(Payload):
    channel_dna: dict[str, Any]
    expected_head_revision: int | None = None
    expected_head_artifact_id: str | None = None


class DnaApproval(Payload):
    expected_head_revision: int | None
    expected_sha256: str
    actor: str = Field(min_length=1, max_length=200)
    reviewed_at: str = Field(min_length=1, max_length=80)


Limit = Annotated[int, Query(ge=1, le=100)]
Idempotency = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)]


@app.get("/health")
def health(request: Request):
    if not request.app.state.ready:
        return err_json(request, "NOT_READY", "Animation database not ready", 503)
    return enveloped(request, {"status": "ok", "product": "2D Animation Studio"})


@app.get("/api/v1/system")
def system(request: Request):
    if not request.app.state.ready:
        return err_json(request, "NOT_READY", "Animation database not ready", 503)
    return enveloped(request, {
        "product": "2D Animation Studio", "api_schema_version": "api.v1",
        "database_revision": "0001_animation_initial",
        "stages": list(svc.STAGES), "animation_generation_ready": False,
        "disabled_phases": ["C4", "C5", "C6", "C7"],
    })


@app.get("/api/v1/channels")
def channels(request: Request, limit: Limit = 50, cursor: str | None = None):
    return enveloped(request, svc.list_channels(limit, cursor))


@app.post("/api/v1/channels")
def create_channel(request: Request, body: ChannelCreate, idem: Idempotency):
    return enveloped(request, svc.create_channel(body.model_dump(), idem), 201)


@app.get("/api/v1/channels/{channel_id}")
def channel(request: Request, channel_id: str):
    return enveloped(request, svc.get_channel(channel_id))


@app.patch("/api/v1/channels/{channel_id}")
def update_channel(request: Request, channel_id: str, body: ChannelUpdate):
    return enveloped(request, svc.update_channel(
        channel_id, body.expected_updated_at, body.model_dump(exclude_none=True)))


@app.delete("/api/v1/channels/{channel_id}")
def archive_channel(request: Request, channel_id: str, body: Archive):
    return enveloped(request, svc.archive_channel(channel_id, body.expected_updated_at))


@app.get("/api/v1/channels/{channel_id}/dna")
def dna(request: Request, channel_id: str):
    return enveloped(request, svc.dna_head(channel_id))


@app.put("/api/v1/channels/{channel_id}/dna")
def save_dna(request: Request, channel_id: str, body: DnaRevision, idem: Idempotency):
    return enveloped(request, svc.save_dna(
        channel_id, body.channel_dna, body.expected_head_revision,
        body.expected_head_artifact_id, idem), 201)


@app.post("/api/v1/channels/{channel_id}/dna/{artifact_id}/approve")
def approve_dna(request: Request, channel_id: str, artifact_id: str, body: DnaApproval):
    return enveloped(request, svc.approve_dna(
        channel_id, artifact_id, expected_revision=body.expected_head_revision,
        expected_sha=body.expected_sha256, actor=body.actor, reviewed_at=body.reviewed_at))


@app.get("/api/v1/projects")
def projects(request: Request, channel_id: str, limit: Limit = 50, cursor: str | None = None):
    return enveloped(request, svc.list_projects(channel_id, limit, cursor))


@app.post("/api/v1/projects")
def create_project(request: Request, body: ProjectCreate, idem: Idempotency):
    return enveloped(request, svc.create_project(body.model_dump(), idem), 201)


@app.get("/api/v1/projects/{project_id}")
def project(request: Request, project_id: str):
    return enveloped(request, svc.get_project(project_id))


@app.patch("/api/v1/projects/{project_id}")
def update_project(request: Request, project_id: str, body: ChannelUpdate):
    return enveloped(request, svc.update_project(
        project_id, body.expected_updated_at, body.model_dump(exclude_none=True)))


@app.delete("/api/v1/projects/{project_id}")
def archive_project(request: Request, project_id: str, body: Archive):
    return enveloped(request, svc.update_project(project_id, body.expected_updated_at, {}, archive=True))


@app.get("/api/v1/projects/{project_id}/workflow")
def workflow(request: Request, project_id: str):
    return enveloped(request, svc.workflow(project_id))


@app.get("/api/v1/jobs")
def jobs(request: Request, project_id: str, limit: Limit = 50, cursor: str | None = None):
    return enveloped(request, svc.jobs(project_id, limit, cursor))


@app.get("/api/v1/jobs/{job_id}")
def job(request: Request, job_id: str, project_id: str):
    return enveloped(request, svc.job(job_id, project_id))


@app.get("/api/v1/artifacts/{artifact_id}")
def artifact(request: Request, artifact_id: str, channel_id: str):
    return enveloped(request, svc.artifact(artifact_id, channel_id))


# C3 external-authoring endpoints. All operations return the existing envelope.
class AuthoringPrompt(Payload):
    expected_source_fingerprint: str | None = None

class AuthoringImport(Payload):
    reservation_id: str
    document: dict[str, Any]

class AuthoringApproval(Payload):
    expected_head_revision: int
    expected_sha256: str

@app.post("/api/v1/projects/{project_id}/authoring/{artifact_kind}/prompt")
def authoring_prompt(request: Request, project_id: str, artifact_kind: str, body: AuthoringPrompt):
    pkg = auth.prompt(project_id, artifact_kind)
    if body.expected_source_fingerprint is not None and body.expected_source_fingerprint != pkg["source_fingerprint"]:
        svc.error("STALE_HEAD", "Authoring source changed")
    return enveloped(request, pkg, 201)

@app.post("/api/v1/projects/{project_id}/authoring/{artifact_kind}/validate")
def authoring_validate(request: Request, project_id: str, artifact_kind: str, body: AuthoringImport):
    return enveloped(request, auth.validate(project_id, artifact_kind, body.reservation_id, body.document))

@app.post("/api/v1/projects/{project_id}/authoring/{artifact_kind}/import")
def authoring_import(request: Request, project_id: str, artifact_kind: str, body: AuthoringImport):
    return enveloped(request, auth.import_revision(project_id, artifact_kind, body.reservation_id, body.document), 201)

@app.post("/api/v1/projects/{project_id}/authoring/{artifact_kind}/{artifact_id}/approve")
def authoring_approve(request: Request, project_id: str, artifact_kind: str, artifact_id: str, body: AuthoringApproval):
    result=auth.approve(project_id, artifact_kind, artifact_id,
                        body.expected_head_revision, body.expected_sha256)
    if artifact_kind=="shot-plan": assets.publish_requirements(project_id)
    return enveloped(request, result)

@app.get("/api/v1/projects/{project_id}/authoring/{artifact_kind}/history")
def authoring_history(request: Request, project_id: str, artifact_kind: str, limit: Limit = 50):
    return enveloped(request, auth.history(project_id, artifact_kind, limit))

@app.get("/api/v1/projects/{project_id}/authoring/revisions/{artifact_id}")
def authoring_document(request: Request, project_id: str, artifact_id: str):
    return enveloped(request, auth.document(project_id, artifact_id))


# C3 Resolver / local image production. Upload is multipart and explicitly bounded.
class AssetBind(Payload):
    requirement_id: str
    asset_version_id: str
    expected_fingerprint: str

class AssetUnbind(Payload):
    expected_fingerprint: str

class ReviewAsset(Payload):
    decision: str

@app.get("/api/v1/projects/{project_id}/resolver/requirements")
def resolver_requirements(request:Request,project_id:str):
    return enveloped(request, assets.requirements(project_id))

@app.get("/api/v1/projects/{project_id}/resolver/resolution")
def resolver_resolution(request:Request,project_id:str):
    return enveloped(request, assets.resolution(project_id))

@app.get("/api/v1/channels/{channel_id}/assets")
def list_asset_versions(request:Request,channel_id:str,limit:Limit=50):
    return enveloped(request,assets.versions(channel_id,limit))

@app.get("/api/v1/projects/{project_id}/asset-bindings")
def list_project_bindings(request:Request,project_id:str):
    return enveloped(request,{"items":assets.bindings(project_id),"next_cursor":None})

@app.post("/api/v1/projects/{project_id}/asset-bindings")
def bind_asset(request:Request,project_id:str,body:AssetBind):
    result=assets.bind(project_id,body.requirement_id,
                       body.asset_version_id,body.expected_fingerprint)
    assets.publish_resolution(project_id)
    return enveloped(request,result)

@app.delete("/api/v1/projects/{project_id}/asset-bindings/{binding_id}")
def unbind_asset(request:Request,project_id:str,binding_id:str,body:AssetUnbind):
    return enveloped(request,assets.unbind(project_id,binding_id,body.expected_fingerprint))

@app.post("/api/v1/projects/{project_id}/images/import")
async def import_local_image(request:Request,project_id:str,
        file:UploadFile=File(...),kind:str=Form(...),semantic_key:str=Form(...),view:str=Form(...)):
    body=await file.read(localimages.MAX_BYTES+1)
    return enveloped(request,localimages.ingest(project_id,kind,semantic_key,view,body,file.filename or "image"),201)

@app.post("/api/v1/projects/{project_id}/assets/{version_id}/review")
def review_local_image(request:Request,project_id:str,version_id:str,body:ReviewAsset):
    return enveloped(request,localimages.review(project_id,version_id,body.decision))

@app.get("/api/v1/projects/{project_id}/assets/{version_id}/image")
def local_image_preview(request:Request,project_id:str,version_id:str):
    path,mime=localimages.read_image(project_id,version_id)
    return FileResponse(path,media_type=mime)


# G-Labs: consent recorded durably before any user-initiated paid submission.
class GenerationPrepare(Payload):
    requirement_id: str
    prompt: str
    negative_prompt: str = ""
    model: str = "nano_banana_2"
    aspect_ratio: str = "1:1"
    cost_ceiling_usd: float = Field(gt=0,le=100)

class GenerationConfirm(Payload):
    quote: dict[str, Any]
    fingerprint: str
    explicitly_approved: bool

@app.get("/api/v1/projects/{project_id}/generation/provider")
def glabs_provider(request:Request,project_id:str):
    svc.get_project(project_id)
    return enveloped(request,glabs.configuration())

@app.post("/api/v1/projects/{project_id}/generation/prepare")
def glabs_prepare(request:Request,project_id:str,body:GenerationPrepare):
    return enveloped(request,glabs.prepare(project_id,body.requirement_id,body.prompt,
                       body.negative_prompt,body.model,body.aspect_ratio,body.cost_ceiling_usd),201)

@app.post("/api/v1/projects/{project_id}/generation/confirm")
def glabs_confirm(request:Request,project_id:str,body:GenerationConfirm,idem:Idempotency):
    return enveloped(request,glabs.confirm(project_id,body.quote,body.fingerprint,
                       idem,body.explicitly_approved),202)

@app.get("/api/v1/projects/{project_id}/generation/operations/{operation_id}")
def glabs_status(request:Request,project_id:str,operation_id:str):
    return enveloped(request,glabs.status(project_id,operation_id))

@app.post("/api/v1/projects/{project_id}/generation/operations/{operation_id}/advance")
def glabs_advance(request:Request,project_id:str,operation_id:str):
    return enveloped(request,glabs.advance(project_id,operation_id),202)

@app.post("/api/v1/projects/{project_id}/generation/operations/{operation_id}/cancel")
def glabs_cancel(request:Request,project_id:str,operation_id:str):
    return enveloped(request,glabs.cancel(project_id,operation_id),202)

@app.get("/api/v1/projects/{project_id}/generation/operations")
def glabs_operations(request:Request,project_id:str):
    return enveloped(request,glabs.list_operations(project_id))

class GenerationReconcile(Payload):
    provider_task_id: str
    confirmed_owner_match: bool

@app.post("/api/v1/projects/{project_id}/generation/operations/{operation_id}/reconcile")
def glabs_reconcile(request: Request, project_id: str, operation_id: str, body: GenerationReconcile):
    return enveloped(request, glabs.reconcile_unknown(project_id, operation_id,
              body.provider_task_id, body.confirmed_owner_match), 202)
