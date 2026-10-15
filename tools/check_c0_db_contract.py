"""Executable C0-only proof for the frozen SQLite schema; never opens a user DB."""
from __future__ import annotations

import hashlib
import sqlite3
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DDL = ROOT / "contracts/animation/animation_schema.sql"
EXPECTED_TABLES = {
    "channels", "projects", "project_stage_heads", "artifacts", "authoring_reservations",
    "assets", "asset_versions", "project_asset_bindings", "rigs", "rig_versions",
    "motion_templates", "operations", "operation_tasks", "jobs",
}
LEGACY_TABLES = {"scene_plans", "beats", "voice_generation_operations", "render_operations", "style_bibles"}


def connect(path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(path, isolation_level=None)
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=1000")
    return db


def install(db: sqlite3.Connection) -> None:
    db.executescript(DDL.read_text(encoding="utf-8"))


def refuse_legacy_read_only(path: Path) -> None:
    uri = f"file:{path.as_posix()}?mode=ro"
    db = sqlite3.connect(uri, uri=True)
    try:
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        revisions = {row[0] for row in db.execute("SELECT version_num FROM alembic_version")} if "alembic_version" in tables else set()
        if tables & LEGACY_TABLES or any(rev[:3].isdigit() and 1 <= int(rev[:3]) <= 31 for rev in revisions):
            raise RuntimeError("LEGACY_DATABASE_UNSUPPORTED")
    finally:
        db.close()


def seed_channel_project(db: sqlite3.Connection) -> None:
    h = "a" * 64
    db.execute("INSERT INTO channels VALUES (?,?,?,?,?,?,?,?,?)", ("ch_a", "A", "a", None, h, h, h, "t", "t"))
    db.execute("INSERT INTO projects VALUES (?,?,?,?,?,?,?)", ("pr_a", "ch_a", "P", "p", "active", "t", "t"))


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="c0-db-proof-") as folder:
        path = Path(folder) / "proof.sqlite"
        db = connect(path)
        install(db)
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        assert tables == EXPECTED_TABLES, (tables - EXPECTED_TABLES, EXPECTED_TABLES - tables)
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        seed_channel_project(db)
        artifact = ("dna_1", "ch_a", None, "channel_dna", "channel_dna.v2", "current", 1, "approved", "b" * 64, 2, "ch/dna1.json", "[]", "{}", "{}", "test", "t", "test", "t")
        db.execute("INSERT INTO artifacts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", artifact)
        try:
            db.execute("INSERT INTO artifacts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ("dna_2", *artifact[1:6], 1, *artifact[7:10], "ch/dna2.json", *artifact[11:]))
        except sqlite3.IntegrityError:
            pass
        else:
            raise AssertionError("nullable ChannelDNA uniqueness was not enforced")
        db.close()
    print("PASS tables=14 foreign_keys=clean nullable_channel_revision=rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
