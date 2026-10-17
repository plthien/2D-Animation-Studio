"""Gate C2-02 focused schema and legacy data integrity tests."""
from __future__ import annotations

import hashlib
from contextlib import closing
import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import inspect

from app.animation.database import (
    APPLICATION_TABLES, SCHEMA_REVISION, LegacyDatabaseUnsupported,
    connect, guard_database, migrate,
)


def test_fresh_schema_exact_tables_and_indexes(tmp_path: Path, monkeypatch):
    url = "sqlite:///" + str(tmp_path / "fresh.db").replace("\\", "/")
    monkeypatch.setenv("DATABASE_URL", url)
    migrate(url)
    with connect(url) as conn:
        names = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )}
        assert names == APPLICATION_TABLES | {"alembic_version"}
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone()[0] == SCHEMA_REVISION
        indexes = {r[0]: r[1] for r in conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL"
        )}
        assert "WHERE project_id IS NULL" in indexes["ux_artifacts_channel_revision"]
        assert "WHERE project_id IS NOT NULL" in indexes["ux_artifacts_project_revision"]
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert {r[1] for r in conn.execute("PRAGMA table_info(project_stage_heads)")} >= {
            "project_id", "stage_key", "approval_status", "dependency_fingerprint", "revision"
        }
    migrate(url)


def test_legacy_refused_without_writing_single_byte(tmp_path: Path):
    path = tmp_path / "user_legacy.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE scene_assets (id INTEGER PRIMARY KEY)")
        conn.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        conn.execute("INSERT INTO alembic_version VALUES ('031_voice_generation_providers')")
    baseline = hashlib.sha256(path.read_bytes()).hexdigest()
    url = "sqlite:///" + str(path).replace("\\", "/")
    with pytest.raises(LegacyDatabaseUnsupported, match="LEGACY_DATABASE_UNSUPPORTED"):
        guard_database(url)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == baseline


def test_unknown_database_rejected_without_clobber(tmp_path: Path):
    path = tmp_path / "unrelated.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE customer_orders (id INTEGER)")
    before = path.read_bytes()
    with pytest.raises(LegacyDatabaseUnsupported):
        guard_database("sqlite:///" + str(path).replace("\\", "/"))
    assert path.read_bytes() == before


def test_migration_matches_every_frozen_create_sql(tmp_path: Path, monkeypatch):
    """Every table and explicit index must match normative frozen DDL."""
    import re
    from app.animation.database import migrate
    canonical_path = Path(__file__).resolve().parents[2] / "contracts/animation/animation_schema.sql"
    normative = sqlite3.connect(":memory:")
    try:
        normative.executescript(canonical_path.read_text(encoding="utf-8"))
        expected = {name: sql for name, sql in normative.execute(
            "SELECT name,sql FROM sqlite_master WHERE type IN ('table','index') "
            "AND name NOT LIKE 'sqlite_%' AND sql IS NOT NULL"
        )}
    finally:
        normative.close()
    url = "sqlite:///" + (tmp_path / "exact-ddl.sqlite").as_posix()
    monkeypatch.setenv("DATABASE_URL", url)
    migrate(url)
    with sqlite3.connect(tmp_path / "exact-ddl.sqlite") as conn:
        actual = {name: sql for name, sql in conn.execute(
            "SELECT name,sql FROM sqlite_master WHERE type IN ('table','index') "
            "AND name NOT LIKE 'sqlite_%' AND name!='alembic_version' AND sql IS NOT NULL"
        )}
        assert set(actual)==set(expected)
        def normalize(sql):
            return re.sub(r"\s+", " ", sql).strip().lower()
        for name in expected:
            assert normalize(expected[name])==normalize(actual[name]), name
        for table in APPLICATION_TABLES:
            assert conn.execute(f"PRAGMA table_info({table})").fetchall()
            assert conn.execute(f"PRAGMA foreign_key_list({table})").fetchall() or table == "channels"


@pytest.mark.parametrize("mutation", [
    "drop_channel_index",
    "drop_project_index",
    "unique_constraint",
    "foreign_key",
    "required_column",
    "partial_predicate",
])
def test_existing_animation_schema_tamper_refused_without_writes(tmp_path, monkeypatch, mutation):
    """Each frozen DDL mutation is detected before migration or startup writes."""
    from app.animation.database import AnimationSchemaIntegrityError
    from fastapi.testclient import TestClient
    from app.main import app
    path=tmp_path / ("tampered_" + mutation + ".db")
    url="sqlite:///" + path.as_posix()
    monkeypatch.setenv("DATABASE_URL",url)
    monkeypatch.setenv("ARTIFACT_ROOT",str(tmp_path / "artifacts"))
    migrate(url)

    with closing(sqlite3.connect(path)) as conn:
        # Use a disposable test DB and checkpoint before the corruption baseline.
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.execute("PRAGMA journal_mode=DELETE")
        if mutation == "drop_channel_index":
            conn.execute("DROP INDEX ux_artifacts_channel_revision")
        elif mutation == "drop_project_index":
            conn.execute("DROP INDEX ux_artifacts_project_revision")
        else:
            targets = {
                "unique_constraint": (
                    "projects", "UNIQUE(channel_id, slug), UNIQUE(project_id, channel_id)",
                    "UNIQUE(project_id, channel_id)",
                ),
                "foreign_key": (
                    "projects", "channel_id TEXT NOT NULL REFERENCES channels(channel_id) ON DELETE RESTRICT",
                    "channel_id TEXT NOT NULL",
                ),
                "required_column": (
                    "projects", "name TEXT NOT NULL CHECK(length(name) BETWEEN 1 AND 200),",
                    "",
                ),
                "partial_predicate": (
                    "ux_artifacts_channel_revision", "WHERE project_id IS NULL",
                    "WHERE project_id IS NOT NULL",
                ),
            }
            object_name,source,target=targets[mutation]
            original=conn.execute("SELECT sql FROM sqlite_schema WHERE name=?",(object_name,)).fetchone()[0]
            assert source in original, mutation
            conn.execute("PRAGMA writable_schema=ON")
            conn.execute("UPDATE sqlite_schema SET sql=? WHERE name=?",
                         (original.replace(source,target),object_name))
            conn.execute("PRAGMA writable_schema=OFF")
            conn.execute("PRAGMA schema_version=100")
        conn.commit()
    paths=[path,Path(str(path)+"-wal"),Path(str(path)+"-shm"),Path(str(path)+"-journal")]
    baseline={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.exists()}

    for operation in (lambda:guard_database(url),lambda:migrate(url)):
        with pytest.raises(AnimationSchemaIntegrityError) as caught:
            operation()
        assert caught.value.code=="ANIMATION_SCHEMA_INTEGRITY_INVALID"
        assert {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.exists()}==baseline
    monkeypatch.setenv("AUTO_APPLY_MIGRATIONS","false")
    with pytest.raises(AnimationSchemaIntegrityError):
        with TestClient(app):
            pass
    assert {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.exists()}==baseline


def test_existing_valid_database_manual_startup_and_restart(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    path=tmp_path/"existing_animation.db"
    url="sqlite:///"+path.as_posix()
    monkeypatch.setenv("DATABASE_URL",url)
    migrate(url)
    monkeypatch.setenv("AUTO_APPLY_MIGRATIONS","false")
    with TestClient(app) as client:
        assert client.get("/health").status_code==200
    with TestClient(app) as client:
        assert client.get("/api/v1/system").status_code==200
