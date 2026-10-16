"""Fresh animation SQLite bootstrap. Never migrate, delete or modify a YTB database."""
from __future__ import annotations

import os
import sqlite3
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


class LegacyDatabaseUnsupported(RuntimeError):
    code = "LEGACY_DATABASE_UNSUPPORTED"


def database_path(url: str | None = None) -> Path:
    """Resolve only file-backed SQLite URLs; no ambiguous external database."""
    value = url or os.environ.get("DATABASE_URL", DEFAULT_URL)
    if not value.startswith("sqlite:///") or value == "sqlite:///:memory:":
        raise ValueError("Only file-backed SQLite database URLs are supported")
    result = Path(value[len("sqlite:///"):]).expanduser()
    if not str(result).strip():
        raise ValueError("DATABASE_URL requires a file path")
    return result.resolve()


def guard_database(url: str | None = None) -> Path:
    """Read-only inspection BEFORE any journal/pragma/migration write occurs."""
    path = database_path(url)
    if not path.exists():
        return path
    if not path.is_file():
        raise LegacyDatabaseUnsupported("Configured database is not a regular file")
    try:
        with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=1) as conn:
            names = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%'"
            )}
            if not names:
                return path
            allowed = APPLICATION_TABLES | {"alembic_version"}
            if not names.issubset(allowed) or "alembic_version" not in names:
                raise LegacyDatabaseUnsupported(
                    "LEGACY_DATABASE_UNSUPPORTED: choose a fresh animation database; "
                    "existing database was not modified"
                )
            revisions = {r[0] for r in conn.execute("SELECT version_num FROM alembic_version")}
            if revisions != {SCHEMA_REVISION} or not APPLICATION_TABLES.issubset(names):
                raise LegacyDatabaseUnsupported(
                    "LEGACY_DATABASE_UNSUPPORTED: unrecognized migration lineage; "
                    "existing database was not modified"
                )
    except sqlite3.DatabaseError as exc:
        raise LegacyDatabaseUnsupported(
            "LEGACY_DATABASE_UNSUPPORTED: unable to verify the configured database"
        ) from exc
    return path


def connect(url: str | None = None) -> sqlite3.Connection:
    path = guard_database(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=5, isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA journal_mode=WAL")
    except Exception:
        conn.close()
        raise
    return conn


def migrate(url: str | None = None) -> Path:
    value = url or os.environ.get("DATABASE_URL", DEFAULT_URL)
    path = guard_database(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    ini = Path(__file__).resolve().parents[2] / "alembic.ini"
    cfg = Config(str(ini))
    cfg.set_main_option("script_location", str(ini.parent / "alembic"))
    cfg.set_main_option("sqlalchemy.url", value.replace("%", "%%"))
    command.upgrade(cfg, "head")
    with connect(value) as conn:
        names = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )}
        if names != APPLICATION_TABLES | {"alembic_version"}:
            raise RuntimeError("Fresh animation schema did not match frozen 14-table contract")
        if conn.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise RuntimeError("Animation database has foreign-key violations")
    return path
