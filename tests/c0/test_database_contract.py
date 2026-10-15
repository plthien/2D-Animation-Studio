from __future__ import annotations

import hashlib
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from check_c0_db_contract import EXPECTED_TABLES, connect, install, refuse_legacy_read_only, seed_channel_project  # noqa: E402

H = "a" * 64


@pytest.fixture()
def db(tmp_path: Path):
    connection = connect(tmp_path / "schema.sqlite")
    install(connection)
    seed_channel_project(connection)
    yield connection
    connection.close()


def artifact(artifact_id: str, revision: int, relative: str, project_id: str | None = None, channel: str = "ch_a") -> tuple:
    return (artifact_id, channel, project_id, "channel_dna" if project_id is None else "shot_plan", "channel_dna.v2" if project_id is None else "shot_plan.v1", "current", revision, "approved", H, 10, relative, "[]", "{}", "{}", "test", "2026-01-01T00:00:00Z", "test", "2026-01-01T00:00:00Z")


def test_exact_fourteen_tables_and_foreign_key_graph(db: sqlite3.Connection) -> None:
    tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
    assert tables == EXPECTED_TABLES
    assert db.execute("PRAGMA foreign_keys").fetchone() == (1,)
    assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    indexes = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    assert {"ux_artifacts_channel_revision", "ux_artifacts_project_revision"} <= indexes


def test_nullable_channel_revision_uniqueness_and_next_revision(db: sqlite3.Connection) -> None:
    db.execute("INSERT INTO artifacts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", artifact("dna_1", 1, "dna/1.json"))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO artifacts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", artifact("dna_dup", 1, "dna/dup.json"))
    db.execute("INSERT INTO artifacts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", artifact("dna_2", 2, "dna/2.json"))


def test_cross_project_stage_artifact_and_cross_channel_binding_rejected(db: sqlite3.Connection) -> None:
    db.execute("INSERT INTO projects VALUES (?,?,?,?,?,?,?)", ("pr_b", "ch_a", "B", "b", "active", "t", "t"))
    db.execute("INSERT INTO artifacts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", artifact("shot_b", 1, "b/shot.json", "pr_b"))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO project_stage_heads VALUES (?,?,?,?,?,?,?,?,?)", ("pr_a", "ch_a", "authoring", "shot_b", "approved", H, 1, "t", "t"))
    db.execute("INSERT INTO channels VALUES (?,?,?,?,?,?,?,?,?)", ("ch_b", "B", "b", None, H, H, H, "t", "t"))
    db.execute("INSERT INTO assets VALUES (?,?,?,?,?,?,?)", ("asset_b", "ch_b", "actor", "hero", "front", "t", "t"))
    db.execute("INSERT INTO artifacts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", artifact("asset_art_b", 1, "b/asset.json", None, "ch_b"))
    db.execute("INSERT INTO asset_versions VALUES (?,?,?,?,?,?,?,?,?,?,?)", ("av_b", "asset_b", "ch_b", 1, "asset_art_b", H, H, "approved", H, "t", "t"))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO project_asset_bindings VALUES (?,?,?,?,?,?,?,?,?)", ("bind_bad", "pr_a", "ch_a", "asset_b", "av_b", "hero", H, "t", "t"))


def test_invalid_states_and_stage_keys_rejected(db: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE projects SET status='legacy' WHERE project_id='pr_a'")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO project_stage_heads VALUES (?,?,?,?,?,?,?,?,?)", ("pr_a", "ch_a", "scene_breakdown", None, "draft", H, 0, "t", "t"))


def test_compare_and_set_has_one_winner(tmp_path: Path) -> None:
    path = tmp_path / "cas.sqlite"
    owner = connect(path); install(owner); seed_channel_project(owner)
    owner.execute("INSERT INTO project_stage_heads VALUES (?,?,?,?,?,?,?,?,?)", ("pr_a", "ch_a", "authoring", None, "draft", H, 0, "t", "t"))
    writer1, writer2 = connect(path), connect(path)
    assert writer1.execute("UPDATE project_stage_heads SET revision=1 WHERE project_id='pr_a' AND stage_key='authoring' AND revision=0").rowcount == 1
    assert writer2.execute("UPDATE project_stage_heads SET revision=1 WHERE project_id='pr_a' AND stage_key='authoring' AND revision=0").rowcount == 0
    writer1.close(); writer2.close(); owner.close()


def test_outer_flushed_writer_contract_detects_transaction_before_publish(db: sqlite3.Connection) -> None:
    db.execute("BEGIN IMMEDIATE")
    db.execute("UPDATE projects SET updated_at='flushed' WHERE project_id='pr_a'")
    assert db.in_transaction
    with pytest.raises(sqlite3.OperationalError):
        db.execute("BEGIN IMMEDIATE")
    db.rollback()


def test_legacy_refusal_is_read_only(tmp_path: Path) -> None:
    path = tmp_path / "legacy.sqlite"
    legacy = sqlite3.connect(path)
    legacy.executescript("CREATE TABLE alembic_version(version_num TEXT); INSERT INTO alembic_version VALUES ('031_voice_generation_providers'); CREATE TABLE beats(id TEXT);")
    legacy.close()
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(RuntimeError, match="LEGACY_DATABASE_UNSUPPORTED"):
        refuse_legacy_read_only(path)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
