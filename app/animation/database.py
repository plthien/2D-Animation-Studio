"""Animation-only SQLite bootstrap with read-only frozen-schema attestation."""
from __future__ import annotations

import os
import sqlite3
from functools import lru_cache
from contextlib import closing
from pathlib import Path

from alembic import command
from alembic.config import Config

APPLICATION_TABLES = frozenset({
    "channels", "projects", "artifacts", "project_stage_heads",
    "authoring_reservations", "assets", "asset_versions",
    "project_asset_bindings", "rigs", "rig_versions",
    "motion_templates", "operations", "operation_tasks", "jobs",
})
SCHEMA_REVISION = "0001_animation_initial"
DEFAULT_URL = "sqlite:///./2d_animation_studio.db"
_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "contracts/animation/animation_schema.sql"


class LegacyDatabaseUnsupported(RuntimeError):
    code = "LEGACY_DATABASE_UNSUPPORTED"


class AnimationSchemaIntegrityError(RuntimeError):
    """Recognized animation DB with a corrupted or altered frozen schema."""
    code = "ANIMATION_SCHEMA_INTEGRITY_INVALID"


def database_path(url: str | None = None) -> Path:
    """Resolve only file-backed SQLite URLs; no ambiguous external database."""
    value = url or os.environ.get("DATABASE_URL", DEFAULT_URL)
    if not value.startswith("sqlite:///") or value == "sqlite:///:memory:":
        raise ValueError("Only file-backed SQLite database URLs are supported")
    result = Path(value[len("sqlite:///"):]).expanduser()
    if not str(result).strip():
        raise ValueError("DATABASE_URL requires a file path")
    return result.resolve()


def _normalize_ddl(sql: str | None) -> str | None:
    """Normalize only non-quoted whitespace and case, never SQL literal data."""
    if sql is None:
        return None
    out = []
    quote = None
    for ch in sql:
        if quote is not None:
            out.append(ch)
            if ch == quote:
                quote = None
        elif ch in ("'", '"', "`", "["):
            quote = "]" if ch == "[" else ch
            out.append(ch)
        elif ch.isspace():
            if out and out[-1] != " ":
                out.append(" ")
        else:
            out.append(ch.lower())
    return "".join(out).strip()


def _schema_signature(con: sqlite3.Connection) -> tuple:
    """Compare all frozen DDL + structural PRAGMAs; preserve CHECK predicates.

    Exact SQLite-stored SQL is intentionally stricter than heuristic normalizing:
    quotes, CHECK clauses, collation and partial WHERE predicates are semantic.
    Cosmetic third-party rewrites are not a supported migration of this frozen DB.
    """
    objects = tuple((kind, name, table, _normalize_ddl(sql)) for kind, name, table, sql in con.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_schema "
        "WHERE name NOT LIKE 'sqlite_%' AND name!='alembic_version' AND type IN ('table','index','view','trigger') "
        "ORDER BY type,name"
    ))
    tables = sorted(APPLICATION_TABLES)
    structure = []
    for table in tables:
        quoted = '"' + table.replace('"', '""') + '"'
        structure.append((
            table,
            tuple(con.execute(f"PRAGMA table_xinfo({quoted})")),
            tuple(con.execute(f"PRAGMA foreign_key_list({quoted})")),
            tuple(con.execute(f"PRAGMA index_list({quoted})")),
        ))
        for item in con.execute(f"PRAGMA index_list({quoted})"):
            ix = '"' + str(item[1]).replace('"', '""') + '"'
            structure.append((item[1], tuple(con.execute(f"PRAGMA index_xinfo({ix})"))))
    return objects, tuple(structure)


@lru_cache(maxsize=1)
def _normative_schema_signature() -> tuple:
    """Load frozen normative DDL only into a disposable in-memory connection."""
    with closing(sqlite3.connect(":memory:")) as reference:
        reference.executescript(_SCHEMA_PATH.read_text(encoding="utf-8"))
        return _schema_signature(reference)


def verify_frozen_schema(con: sqlite3.Connection) -> None:
    """Read-only verification, including SQLite foreign-key integrity."""
    try:
        actual = _schema_signature(con)
        expected = _normative_schema_signature()
        if actual != expected:
            raise AnimationSchemaIntegrityError(
                "ANIMATION_SCHEMA_INTEGRITY_INVALID: frozen animation schema differs"
            )
        version_cols = tuple(con.execute('PRAGMA table_info("alembic_version")'))
        if len(version_cols) != 1 or version_cols[0][1:4] != ("version_num", "VARCHAR(32)", 1):
            raise AnimationSchemaIntegrityError(
                "ANIMATION_SCHEMA_INTEGRITY_INVALID: migration version table differs"
            )
        if con.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise AnimationSchemaIntegrityError(
                "ANIMATION_SCHEMA_INTEGRITY_INVALID: foreign-key integrity check failed"
            )
    except sqlite3.DatabaseError as exc:
        raise AnimationSchemaIntegrityError(
            "ANIMATION_SCHEMA_INTEGRITY_INVALID: unable to inspect animation database"
        ) from exc


def guard_database(url: str | None = None) -> Path:
    """Inspect before any migration or WAL write; never convert old user data."""
    path = database_path(url)
    if not path.exists():
        return path
    if not path.is_file():
        raise LegacyDatabaseUnsupported("LEGACY_DATABASE_UNSUPPORTED: not a database file")
    try:
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=1)) as con:
            # Read-only connection and connection-local PRAGMA: inspect raw
            # malformed DDL, then compare against the frozen normative schema.
            con.execute("PRAGMA writable_schema=ON")
            names = {r[0] for r in con.execute(
                "SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )}
            if not names:
                return path
            allowed = APPLICATION_TABLES | {"alembic_version"}
            if not names.issubset(allowed) or "alembic_version" not in names:
                raise LegacyDatabaseUnsupported(
                    "LEGACY_DATABASE_UNSUPPORTED: choose a fresh animation database; "
                    "existing database was not modified"
                )
            revisions = {r[0] for r in con.execute("SELECT version_num FROM alembic_version")}
            if revisions != {SCHEMA_REVISION}:
                raise LegacyDatabaseUnsupported(
                    "LEGACY_DATABASE_UNSUPPORTED: unrecognized migration lineage; "
                    "existing database was not modified"
                )
            # Missing known animation tables/constraints is an integrity error,
            # distinct from an unrelated or old YTB database.
            verify_frozen_schema(con)
    except AnimationSchemaIntegrityError:
        raise
    except sqlite3.DatabaseError as exc:
        raise LegacyDatabaseUnsupported(
            "LEGACY_DATABASE_UNSUPPORTED: unable to verify database identity"
        ) from exc
    return path


def connect(url: str | None = None) -> sqlite3.Connection:
    path = guard_database(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path), timeout=5, isolation_level=None)
    con.row_factory = sqlite3.Row
    try:
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("PRAGMA busy_timeout=5000")
        con.execute("PRAGMA journal_mode=WAL")
    except BaseException:
        con.close()
        raise
    return con


def migrate(url: str | None = None) -> Path:
    value = url or os.environ.get("DATABASE_URL", DEFAULT_URL)
    path = guard_database(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    ini = Path(__file__).resolve().parents[2] / "alembic.ini"
    cfg = Config(str(ini))
    cfg.set_main_option("script_location", str(ini.parent / "alembic"))
    cfg.set_main_option("sqlalchemy.url", value.replace("%", "%%"))
    command.upgrade(cfg, "head")
    # Validate the same full frozen structure on freshly migrated databases.
    guard_database(value)
    with closing(connect(value)) as con:
        if con.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
            raise AnimationSchemaIntegrityError(
                "ANIMATION_SCHEMA_INTEGRITY_INVALID: foreign keys disabled"
            )
    return path
