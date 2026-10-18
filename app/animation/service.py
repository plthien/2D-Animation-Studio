"""Single-product animation C2 platform. No legacy runtime imports or worker startup."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator

from jsonschema import Draft202012Validator, FormatChecker
from app.animation.database import connect

STAGES = ("authoring", "resolver", "generation", "rigging", "director", "motion", "delivery")
PHASE = dict(zip(STAGES, ("C3", "C3", "C3", "C4", "C5", "C5", "C6")))
ZERO = "0" * 64
DNA_SCHEMA = json.loads((Path(__file__).resolve().parents[2] /
                          "contracts/animation/schemas/channel_dna.v2.schema.json").read_text(encoding="utf-8"))
DNA_VALIDATOR = Draft202012Validator(DNA_SCHEMA, format_checker=FormatChecker())


class DomainError(Exception):
    def __init__(self, code: str, message: str, status: int = 409, **details: Any):
        self.code, self.message, self.status, self.details = code, message, status, details
        super().__init__(message)


def error(code: str, message: str, status: int = 409, **details: Any) -> None:
    raise DomainError(code, message, status, **details)


def canon(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha(value: Any) -> str:
    return hashlib.sha256(canon(value)).hexdigest()


def uid(prefix: str) -> str:
    return prefix + "_" + uuid.uuid4().hex


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def slug(value: str) -> str:
    value = value.strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,99}", value):
        error("VALIDATION_FAILED", "Slug must be 1–100 ASCII letters, digits, - or _", 422)
    return value


def name(value: str) -> str:
    value = value.strip()
    if not 1 <= len(value) <= 200:
        error("VALIDATION_FAILED", "Name must be 1–200 characters", 422)
    return value


def keyhash(key: str) -> str:
    if not re.fullmatch(r"[\x21-\x7e]{1,128}", key):
        error("VALIDATION_FAILED", "Idempotency-Key must be printable ASCII, length 1–128", 422)
    return hashlib.sha256(key.encode("ascii")).hexdigest()


@contextmanager
def reader() -> Iterator[sqlite3.Connection]:
    con = connect()
    try:
        yield con
    finally:
        con.close()


@contextmanager
def writer() -> Iterator[sqlite3.Connection]:
    con = connect()
    try:
        con.execute("BEGIN IMMEDIATE")
        yield con
        con.commit()
    except BaseException:
        con.rollback()
        raise
    finally:
        con.close()


def forbid_nested_session(session: Any | None) -> None:
    """Reject a preflushed SQLAlchemy transaction instead of starting a competing writer."""
    if session is not None and session.in_transaction():
        error("TRANSACTION_OWNERSHIP_CONFLICT", "Publishing inside an existing Session transaction is forbidden")


def artifact_root() -> Path:
    return Path(os.getenv("ARTIFACT_ROOT", "./local_artifacts")).expanduser().resolve()


def bounded_path(relative: str) -> Path:
    root = artifact_root()
    fragment = Path(relative)
    if not relative or fragment.is_absolute() or ".." in fragment.parts or "\\" in relative or ":" in relative:
        error("VALIDATION_FAILED", "Unsafe artifact path", 422)
    current = root
    for part in fragment.parts:
        current = current / part
        if current.exists() and (current.is_symlink() or getattr(current, "is_junction", lambda: False)()):
            error("VALIDATION_FAILED", "Artifact path contains a reparse link", 422)
    target = current.resolve()
    if not target.is_relative_to(root):
        error("VALIDATION_FAILED", "Artifact path escapes managed root", 422)
    return target


def filehash(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    n = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
            n += len(block)
    return digest.hexdigest(), n


def rowdict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def receipt(con: sqlite3.Connection, channel_id: str, kind: str, key: str) -> sqlite3.Row | None:
    return con.execute(
        "SELECT * FROM artifacts WHERE channel_id=? AND project_id IS NULL AND kind=? AND logical_key=?",
        (channel_id, kind, key),
    ).fetchone()


def add_artifact(
    con: sqlite3.Connection, *, aid: str, channel_id: str, project_id: str | None,
    kind: str, schema: str, logical: str, revision: int, status: str,
    checksum: str, size: int, relative: str, metadata: dict[str, Any],
    created_by: str = "local-user",
) -> None:
    t = now()
    con.execute(
        """INSERT INTO artifacts
        (artifact_id, channel_id, project_id, kind, schema_version, logical_key, revision,
         approval_status, sha256, byte_size, relative_path, parents_json,
         source_fingerprints_json, metadata_json, created_by, created_at, reviewed_by, reviewed_at)
         VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (aid, channel_id, project_id, kind, schema, logical, revision, status,
         checksum, size, relative, "[]", "{}", canon(metadata).decode(),
         created_by, t, created_by if status == "approved" else None, t if status == "approved" else None)
    )


def document_publish(
    document: Any, relative: str, callback: Callable[[sqlite3.Connection, str, int], Any],
    *, session: Any | None = None,
) -> Any:
    forbid_nested_session(session)
    root = artifact_root()
    root.mkdir(parents=True, exist_ok=True)
    final = bounded_path(relative)
    final.parent.mkdir(parents=True, exist_ok=True)
    bounded_path(relative)  # recheck after directory creation
    staging = bounded_path("_staging")
    staging.mkdir(exist_ok=True)
    serialized = canon(document)
    if len(serialized) > 1_048_576:
        error("IMPORT_TOO_LARGE", "C2 JSON metadata exceeds 1 MiB transaction-safe limit", 413)
    fd, scratch = tempfile.mkstemp(prefix="publish-", suffix=".tmp", dir=staging)
    scratch = Path(scratch)
    created = False
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(serialized)
            f.flush()
            os.fsync(f.fileno())
        checksum, size = filehash(scratch)
        with writer() as con:
            result = callback(con, checksum, size)
            # An idempotent retry may return an earlier artifact without
            # inserting a new one. Never finalize attempt-only orphan bytes.
            if not con.execute("SELECT 1 FROM artifacts WHERE relative_path=?", (relative,)).fetchone():
                return result
            if filehash(scratch) != (checksum, size):
                error("LINEAGE_MISMATCH", "Staging changed during publication", 422)
            # Each successful revision gets a UUID-named file. If a retry had
            # already finalized the same file, verify rather than overwrite it.
            final = bounded_path(relative)
            if final.exists():
                if filehash(final) != (checksum, size):
                    error("LINEAGE_MISMATCH", "Artifact file collision", 422)
            else:
                os.replace(scratch, final)
                created = True
                if filehash(final) != (checksum, size):
                    error("LINEAGE_MISMATCH", "Final artifact digest mismatch", 422)
        return result
    except BaseException:
        if created:
            with reader() as con:
                linked = con.execute("SELECT 1 FROM artifacts WHERE relative_path=?", (relative,)).fetchone()
                if not linked:
                    bounded_path(relative).unlink(missing_ok=True)
        raise
    finally:
        scratch.unlink(missing_ok=True)


def channel_row(con: sqlite3.Connection, cid: str) -> dict[str, Any]:
    row = con.execute("SELECT * FROM channels WHERE channel_id=?", (cid,)).fetchone()
    if not row:
        error("NOT_FOUND", "Channel not found", 404)
    data = rowdict(row)
    head = con.execute("SELECT revision FROM artifacts WHERE artifact_id=?", (data["current_dna_artifact_id"],)).fetchone()
    data["current_dna_revision"] = head["revision"] if head else None
    data["status"] = "archived" if con.execute(
        "SELECT 1 FROM artifacts WHERE channel_id=? AND kind='platform.channel_archive.v1'", (cid,)
    ).fetchone() else "active"
    return data


def active_channel(con: sqlite3.Connection, cid: str) -> dict[str, Any]:
    row = channel_row(con, cid)
    if row["status"] != "active":
        error("OWNERSHIP_CONFLICT", "Channel is archived")
    return row


def project_row(con: sqlite3.Connection, pid: str) -> dict[str, Any]:
    row = con.execute("SELECT * FROM projects WHERE project_id=?", (pid,)).fetchone()
    if not row:
        error("NOT_FOUND", "Project not found", 404)
    return rowdict(row)


def create_channel(payload: dict[str, Any], idem: str) -> dict[str, Any]:
    data = {"name": name(payload["name"]), "slug": slug(payload["slug"])}
    h = keyhash(idem)
    cid, aid = "ch_" + h[:32], "ar_" + h[:32]
    rel = f"channels/{cid}/requests/{aid}.json"
    def transaction(con: sqlite3.Connection, checksum: str, size: int):
        prior = con.execute("SELECT metadata_json FROM artifacts WHERE artifact_id=?", (aid,)).fetchone()
        if prior:
            if json.loads(prior["metadata_json"]).get("request_hash") != sha(data):
                error("IDEMPOTENCY_CONFLICT", "Idempotency-Key bound to different request")
            return channel_row(con, cid)
        if con.execute("SELECT 1 FROM channels WHERE slug=?", (data["slug"],)).fetchone():
            error("DUPLICATE_SLUG", "Channel slug already exists")
        t = now()
        con.execute(
            "INSERT INTO channels VALUES (?,?,?,?,?,?,?,?,?)",
            (cid, data["name"], data["slug"], None, ZERO, ZERO, ZERO, t, t)
        )
        add_artifact(con, aid=aid, channel_id=cid, project_id=None,
                     kind="platform.channel_create.v1", schema="platform.request.v1",
                     logical=h, revision=1, status="approved", checksum=checksum,
                     size=size, relative=rel, metadata={"request_hash": sha(data)})
        return channel_row(con, cid)
    return document_publish(data, rel, transaction)


def list_channels(limit: int, cursor: str | None) -> dict[str, Any]:
    with reader() as con:
        rows = con.execute(
            "SELECT channel_id FROM channels WHERE channel_id>? ORDER BY channel_id LIMIT ?",
            (cursor or "", limit + 1),
        ).fetchall()
        return {"items": [channel_row(con, r["channel_id"]) for r in rows[:limit]],
                "next_cursor": rows[limit - 1]["channel_id"] if len(rows) > limit else None}


def get_channel(cid: str) -> dict[str, Any]:
    with reader() as con:
        return channel_row(con, cid)


def update_channel(cid: str, expected: str, payload: dict[str, Any]) -> dict[str, Any]:
    with writer() as con:
        old = active_channel(con, cid)
        if old["updated_at"] != expected:
            error("STALE_HEAD", "Channel changed", current_updated_at=old["updated_at"])
        n = name(payload["name"]) if payload.get("name") is not None else old["name"]
        s = slug(payload["slug"]) if payload.get("slug") is not None else old["slug"]
        try:
            con.execute("UPDATE channels SET name=?,slug=?,updated_at=? WHERE channel_id=? AND updated_at=?",
                        (n, s, now(), cid, expected))
        except sqlite3.IntegrityError:
            error("DUPLICATE_SLUG", "Channel slug already exists")
        return channel_row(con, cid)


def archive_channel(cid: str, expected: str) -> dict[str, Any]:
    rel_aid = uid("ar")
    rel = f"channels/{cid}/archive/{rel_aid}.json"
    def transaction(con: sqlite3.Connection, digest: str, size: int):
        current = channel_row(con, cid)
        if current["status"] == "archived":
            return current
        if current["updated_at"] != expected:
            error("STALE_HEAD", "Channel changed", current_updated_at=current["updated_at"])
        if con.execute("SELECT 1 FROM projects WHERE channel_id=? LIMIT 1", (cid,)).fetchone():
            error("OWNERSHIP_CONFLICT", "Channel owns projects and cannot be archived")
        add_artifact(con, aid=rel_aid, channel_id=cid, project_id=None,
                     kind="platform.channel_archive.v1", schema="platform.archive.v1",
                     logical="channel-archive", revision=1, status="approved",
                     checksum=digest, size=size, relative=rel, metadata={})
        con.execute("UPDATE channels SET updated_at=? WHERE channel_id=? AND updated_at=?",
                    (now(), cid, expected))
        return channel_row(con, cid)
    return document_publish({"archive": cid}, rel, transaction)


def dna_head(cid: str) -> dict[str, Any]:
    with reader() as con:
        channel = channel_row(con, cid)
        aid = channel["current_dna_artifact_id"]
        if aid:
            row = con.execute("SELECT * FROM artifacts WHERE artifact_id=?", (aid,)).fetchone()
            p = bounded_path(row["relative_path"])
            if not p.is_file() or filehash(p) != (row["sha256"], row["byte_size"]):
                error("LINEAGE_MISMATCH", "DNA artifact corrupt or missing", 422)
            doc = json.loads(p.read_text(encoding="utf-8"))
        else:
            doc = None
        return {"channel": channel, "head_artifact_id": aid,
                "head_revision": channel["current_dna_revision"], "channel_dna": doc}


def artifact_view(row: sqlite3.Row) -> dict[str, Any]:
    r = rowdict(row)
    for field in ("parents_json", "source_fingerprints_json", "metadata_json"):
        r[field[:-5]] = json.loads(r.pop(field))
    r["relative_artifact_handle"] = r.pop("relative_path")
    return r


def save_dna(cid: str, source: dict[str, Any], expected_revision: int | None,
             expected_aid: str | None, idem: str) -> dict[str, Any]:
    h = keyhash(idem)
    allowed = {"schema_version", "identity", "visual", "performance", "narration"}
    if set(source) - allowed:
        error("VALIDATION_FAILED", "DNA submission contains server-owned or unknown fields", 422)
    request_hash = sha({"source": source, "expected_revision": expected_revision,
                       "expected_head_artifact_id": expected_aid})
    with reader() as con:
        active_channel(con, cid)
        prior = con.execute(
            """SELECT * FROM artifacts WHERE channel_id=? AND kind='channel_dna.v2'
               AND json_extract(metadata_json, '$.idempotency_key_hash')=?""",
            (cid, h),
        ).fetchone()
        if prior:
            if json.loads(prior["metadata_json"])["request_hash"] != request_hash:
                error("IDEMPOTENCY_CONFLICT", "Idempotency-Key reused with different DNA")
            return artifact_view(prior)
    aid = uid("ar")
    rel = f"channels/{cid}/dna/{aid}.json"
    def transaction(con: sqlite3.Connection, digest: str, size: int):
        channel = active_channel(con, cid)
        prior = con.execute(
            """SELECT * FROM artifacts WHERE channel_id=? AND kind='channel_dna.v2'
               AND json_extract(metadata_json, '$.idempotency_key_hash')=?""",
            (cid, h),
        ).fetchone()
        if prior:
            if json.loads(prior["metadata_json"])["request_hash"] != request_hash:
                error("IDEMPOTENCY_CONFLICT", "Idempotency-Key reused with different DNA")
            return artifact_view(prior)
        if channel["current_dna_revision"] != expected_revision or channel["current_dna_artifact_id"] != expected_aid:
            error("STALE_HEAD", "DNA head changed",
                  current_head_artifact_id=channel["current_dna_artifact_id"],
                  current_head_revision=channel["current_dna_revision"])
        rev = con.execute(
            """SELECT COALESCE(MAX(revision), 0)+1 FROM artifacts
               WHERE channel_id=? AND project_id IS NULL AND kind='channel_dna.v2'
                 AND logical_key='channel_dna'""", (cid,)
        ).fetchone()[0]
        return channel, rev
    # Allocate no revision before CAS; callers cannot pretend candidate is approved.
    with reader() as con:
        channel = active_channel(con, cid)
        revision = con.execute(
            """SELECT COALESCE(MAX(revision), 0)+1 FROM artifacts WHERE channel_id=?
               AND project_id IS NULL AND kind='channel_dna.v2' AND logical_key='channel_dna'""",
            (cid,)
        ).fetchone()[0]
    doc = dict(source)
    doc.update({"artifact_id": aid, "channel_id": cid, "revision": revision,
                "created_at": now(), "visual_style_hash": sha(source.get("visual")),
                "performance_style_hash": sha(source.get("performance")),
                "narration_identity_hash": sha(source.get("narration"))})
    failures = sorted(DNA_VALIDATOR.iter_errors(doc), key=lambda e: list(map(str, e.path)))
    if failures:
        error("VALIDATION_FAILED", "ChannelDNA v2 rejected", 422,
              issues=[{"path": "/".join(map(str, e.path)), "message": e.message} for e in failures[:15]])
    def commit_candidate(con: sqlite3.Connection, checksum: str, size: int):
        current, next_revision = transaction(con, checksum, size)
        if next_revision != revision:
            error("STALE_HEAD", "DNA candidate revision changed",
                  current_head_revision=current["current_dna_revision"])
        add_artifact(con, aid=aid, channel_id=cid, project_id=None, kind="channel_dna.v2",
                     schema="channel_dna.v2", logical="channel_dna", revision=revision,
                     status="draft", checksum=checksum, size=size, relative=rel,
                     metadata={"idempotency_key_hash": h, "request_hash": request_hash})
        return artifact_view(con.execute("SELECT * FROM artifacts WHERE artifact_id=?", (aid,)).fetchone())
    return document_publish(doc, rel, commit_candidate)


def approve_dna(cid: str, aid: str, *, expected_revision: int | None,
                expected_sha: str, actor: str, reviewed_at: str) -> dict[str, Any]:
    with writer() as con:
        current = active_channel(con, cid)
        row = con.execute(
            "SELECT * FROM artifacts WHERE artifact_id=? AND channel_id=? AND project_id IS NULL AND kind='channel_dna.v2'",
            (aid, cid),
        ).fetchone()
        if row is None:
            error("NOT_FOUND", "DNA candidate not found", 404)
        if row["sha256"] != expected_sha:
            error("LINEAGE_MISMATCH", "Candidate SHA mismatch", 422)
        if current["current_dna_artifact_id"] == aid and row["approval_status"] == "approved":
            return {"channel": current, "head_artifact_id": aid, "head_revision": row["revision"]}
        if current["current_dna_revision"] != expected_revision:
            error("STALE_HEAD", "DNA approval lost head race",
                  current_head_artifact_id=current["current_dna_artifact_id"],
                  current_head_revision=current["current_dna_revision"])
        # CAS of the expected head is necessary but not sufficient: approving an
        # old draft must never move the live head revision backwards.
        active_revision = current["current_dna_revision"] or 0
        if row["revision"] <= active_revision:
            error("STALE_HEAD", "ChannelDNA candidate is older than the approved head",
                  current_head_artifact_id=current["current_dna_artifact_id"],
                  current_head_revision=current["current_dna_revision"])
        if row["approval_status"] != "draft":
            error("VALIDATION_FAILED", "Only draft DNA can be approved", 422)
        path = bounded_path(row["relative_path"])
        if not path.is_file() or filehash(path) != (row["sha256"], row["byte_size"]):
            error("LINEAGE_MISMATCH", "Candidate DNA file checksum invalid", 422)
        doc = json.loads(path.read_text(encoding="utf-8"))
        update = con.execute(
            """UPDATE channels SET current_dna_artifact_id=?, visual_style_hash=?,
               performance_style_hash=?, narration_identity_hash=?, updated_at=?
               WHERE channel_id=? AND current_dna_artifact_id IS ?""",
            (aid, doc["visual_style_hash"], doc["performance_style_hash"],
             doc["narration_identity_hash"], now(), cid, current["current_dna_artifact_id"]),
        )
        if update.rowcount != 1:
            error("STALE_HEAD", "DNA approval CAS lost")
        con.execute(
            "UPDATE artifacts SET approval_status='approved', reviewed_by=?, reviewed_at=? WHERE artifact_id=? AND approval_status='draft'",
            (actor, reviewed_at, aid),
        )
        return {"channel": channel_row(con, cid), "head_artifact_id": aid,
                "head_revision": row["revision"]}


def style_fingerprint(stage: str, channel: dict[str, Any]) -> str:
    hashes = {}
    if stage in STAGES[1:]:
        hashes["visual_style_hash"] = channel["visual_style_hash"]
    if stage in ("director", "motion", "delivery"):
        hashes["performance_style_hash"] = channel["performance_style_hash"]
    if stage == "delivery":
        hashes["narration_identity_hash"] = channel["narration_identity_hash"]
    return sha({"algorithm_version": "animation-dependencies.v1",
                "stage_key": stage, "sources": [], "style": hashes,
                "contract_versions": ["channel_dna.v2"]})


def create_project(payload: dict[str, Any], idem: str) -> dict[str, Any]:
    cid, n, s = payload["channel_id"], name(payload["name"]), slug(payload["slug"])
    h = sha({"scope": cid, "key": keyhash(idem)})
    pid, aid = "pr_" + h[:32], "ar_" + h[:32]
    data = {"channel_id": cid, "name": n, "slug": s}
    rel = f"projects/{pid}/requests/{aid}.json"
    def transaction(con: sqlite3.Connection, checksum: str, size: int):
        prior = con.execute("SELECT * FROM artifacts WHERE artifact_id=?", (aid,)).fetchone()
        if prior:
            if json.loads(prior["metadata_json"]).get("request_hash") != sha(data):
                error("IDEMPOTENCY_CONFLICT", "Project key reused with different inputs")
            return project_row(con, pid)
        ch = active_channel(con, cid)
        t = now()
        try:
            con.execute(
                "INSERT INTO projects (project_id,channel_id,name,slug,status,created_at,updated_at) VALUES (?,?,?,?,'active',?,?)",
                (pid, cid, n, s, t, t),
            )
        except sqlite3.IntegrityError:
            error("DUPLICATE_SLUG", "Project slug already exists in this channel")
        for stage in STAGES:
            con.execute(
                """INSERT INTO project_stage_heads
                   (project_id, channel_id, stage_key, artifact_id, approval_status,
                    dependency_fingerprint, revision, created_at, updated_at)
                   VALUES (?,?,?,NULL,'draft',?,0,?,?)""",
                (pid, cid, stage, style_fingerprint(stage, ch), t, t),
            )
        # Record exact request idempotency inside the fourteen-table authority.
        add_artifact(con, aid=aid, channel_id=cid, project_id=pid,
                     kind="platform.project_create.v1", schema="platform.request.v1",
                     logical=h, revision=1, status="approved",
                     checksum=checksum, size=size, relative=rel,
                     metadata={"request_hash": sha(data)})
        return project_row(con, pid)
    return document_publish(data, rel, transaction)


def list_projects(cid: str, limit: int, cursor: str | None) -> dict[str, Any]:
    with reader() as con:
        channel_row(con, cid)
        rows = con.execute(
            "SELECT * FROM projects WHERE channel_id=? AND project_id>? ORDER BY project_id LIMIT ?",
            (cid, cursor or "", limit + 1),
        ).fetchall()
        return {"items": [rowdict(r) for r in rows[:limit]],
                "next_cursor": rows[limit-1]["project_id"] if len(rows) > limit else None}


def get_project(pid: str) -> dict[str, Any]:
    with reader() as con:
        return project_row(con, pid)


def update_project(pid: str, expected: str, payload: dict[str, Any], *, archive: bool = False) -> dict[str, Any]:
    with writer() as con:
        old = project_row(con, pid)
        if old["status"] == "archived" and archive:
            return old
        if old["updated_at"] != expected:
            error("STALE_HEAD", "Project changed", current_updated_at=old["updated_at"])
        if old["status"] == "archived":
            error("OWNERSHIP_CONFLICT", "Project archived")
        n = name(payload["name"]) if payload.get("name") is not None else old["name"]
        s = slug(payload["slug"]) if payload.get("slug") is not None else old["slug"]
        try:
            con.execute("UPDATE projects SET name=?,slug=?,status=?,updated_at=? WHERE project_id=? AND updated_at=?",
                        (n, s, "archived" if archive else "active", now(), pid, expected))
        except sqlite3.IntegrityError:
            error("DUPLICATE_SLUG", "Project slug already exists")
        return project_row(con, pid)


def workflow(pid: str) -> dict[str, Any]:
    from app.animation import authoring as a, resolver as r
    with reader() as con:
        pr=project_row(con,pid)
        ch=channel_row(con,pr["channel_id"])
        heads={row["stage_key"]:rowdict(row) for row in con.execute(
            "SELECT * FROM project_stage_heads WHERE project_id=?",(pid,))}
        if set(heads)!=set(STAGES):error("LINEAGE_MISMATCH","Missing stage projections",422)
        topic=a.latest(con,pid,"topic-ideas")
        script=a.latest(con,pid,"script")
        shot=a.latest(con,pid,"shot-plan")
        if not ch["current_dna_artifact_id"]: authoring=("blocked",["CHANNEL_DNA_NOT_APPROVED"])
        elif topic is None:authoring=("ready",["TOPIC_IDEAS_MISSING"])
        elif script is None:authoring=("ready",["SCRIPT_MISSING"])
        elif a.verified_doc(script).get("topic_ideas_artifact_id")!=topic["artifact_id"]:
            authoring=("stale",["SCRIPT_SOURCE_STALE"])
        elif shot is None:authoring=("ready",["SHOT_PLAN_MISSING"])
        else:
            try:r.current_shot(con,pid);authoring=("approved",[])
            except DomainError as exc:authoring=("stale",[exc.code])
        states={"authoring":authoring,"resolver":("blocked",["CURRENT_SHOT_PLAN_REQUIRED"]),
                "generation":("blocked",["CURRENT_SHOT_PLAN_REQUIRED"])}
        resolved=None
        if authoring[0]=="approved":
            try:
                resolved=r.resolution(pid)
                count,total=resolved["resolved_count"],resolved["total_count"]
                states["resolver"]=("approved" if count==total else "draft" if count else "ready",
                                    [] if count==total else ["ASSETS_UNRESOLVED"])
                states["generation"]=("approved" if count==total else "ready",
                                      [] if count==total else ["REQUIRED_ASSETS_MISSING"])
                op=con.execute("""SELECT status FROM operations WHERE project_id=? AND kind='glabs_image'
                               ORDER BY updated_at DESC LIMIT 1""",(pid,)).fetchone()
                if count<total and op:
                    if op["status"] in ("queued","running"):states["generation"]=("running",[])
                    if op["status"]=="unknown":states["generation"]=("blocked",["PROVIDER_SUBMISSION_UNKNOWN"])
                    if op["status"]=="failed":states["generation"]=("failed",["PROVIDER_OPERATION_FAILED"])
                if count<total and states["generation"][0]=="ready":
                    candidate=con.execute("""SELECT 1 FROM artifacts WHERE
                        json_extract(metadata_json,'$.project_id')=? AND kind='asset_version.v1'
                        AND approval_status='draft' LIMIT 1""",(pid,)).fetchone()
                    if candidate:states["generation"]=("draft",["IMAGE_REVIEW_REQUIRED"])
            except DomainError as exc:
                states["resolver"]=("stale",[exc.code])
                states["generation"]=("blocked",["RESOLVER_STALE"])
        stages=[]
        for stage in STAGES:
            head=heads[stage]
            state,blockers=states.get(stage,("blocked",[f"REQUIRES_{PHASE[stage]}"]))
            computed=style_fingerprint(stage,ch)
            if stage=="authoring" and state=="approved":
                computed=head["dependency_fingerprint"]
            if stage=="resolver" and resolved:
                computed=sha({"requirements":resolved["requirements_fingerprint"],
                  "pins":[(x["requirement"]["requirement_id"],x["binding"]["asset_version_id"] if x["binding"] else None)
                          for x in resolved["requirements"]]})
                if state=="approved" and head["approval_status"]=="approved":
                    record=con.execute("SELECT * FROM artifacts WHERE artifact_id=?",(head["artifact_id"],)).fetchone()
                    if record and record["kind"]=="asset_resolution.v1":
                        pins=a.verified_doc(record)["pins"]
                        old={x["requirement_id"]:x["asset_version_id"] for x in pins}
                        current={x["requirement"]["requirement_id"]:x["binding"]["asset_version_id"]
                                 for x in resolved["requirements"] if x["binding"]}
                        if old==current:computed=head["dependency_fingerprint"]
                        else:state,blockers="stale",["RESOLUTION_HEAD_STALE"]
            if stage=="generation" and resolved:
                computed=sha({"requirements":resolved["requirements_fingerprint"],
                              "resolved":resolved["resolved_count"]})
            if pr["status"]=="archived":state,blockers="blocked",["PROJECT_ARCHIVED"]
            stages.append({"stage_key":stage,"approval_status":head["approval_status"],
              "readiness":state,"head_artifact_id":head["artifact_id"],"head_revision":head["revision"],
              "stored_dependency_fingerprint":head["dependency_fingerprint"],
              "computed_dependency_fingerprint":computed,"blocker_codes":blockers,"owner_phase":PHASE[stage]})
        return {"project_id":pid,"channel_id":pr["channel_id"],
          "dependency_fingerprint_algorithm_version":"animation-dependencies.v1","stages":stages}


def jobs(pid: str, limit: int, cursor: str | None) -> dict[str, Any]:
    with reader() as con:
        project_row(con, pid)
        results = con.execute(
            "SELECT * FROM jobs WHERE project_id=? AND job_id>? ORDER BY job_id LIMIT ?",
            (pid, cursor or "", limit+1),
        ).fetchall()
        return {"items": [rowdict(r) for r in results[:limit]],
                "next_cursor": results[limit-1]["job_id"] if len(results)>limit else None}


def job(jid: str, pid: str) -> dict[str, Any]:
    with reader() as con:
        project_row(con, pid)
        row = con.execute("SELECT * FROM jobs WHERE job_id=? AND project_id=?", (jid, pid)).fetchone()
        if not row:
            error("NOT_FOUND", "Job not found", 404)
        return rowdict(row)


def artifact(aid: str, channel_id: str | None = None) -> dict[str, Any]:
    with reader() as con:
        row = con.execute("SELECT * FROM artifacts WHERE artifact_id=?", (aid,)).fetchone()
        if row is None or (channel_id and row["channel_id"] != channel_id):
            error("NOT_FOUND", "Artifact not found", 404)
        return artifact_view(row)
