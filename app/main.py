"""Only supported 2D Animation Studio API. No legacy routes or workers."""
from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager
from typing import Any, Annotated

from fastapi import FastAPI, Header, Query, Request
from fastapi.routing import APIRoute
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.animation import service as svc
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
        "disabled_phases": ["C3", "C4", "C5", "C6", "C7", "C8", "C9", "C10", "C11", "C12"],
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
