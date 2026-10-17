"""Alembic environment for one fresh animation-only database."""
from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, event
from sqlalchemy.pool import NullPool

from app.animation.database import DEFAULT_URL, guard_database

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
url = os.environ.get("DATABASE_URL") or config.get_main_option("sqlalchemy.url") or DEFAULT_URL
if "youtube" in url.lower() and "2d_animation" not in url.lower():
    # The actual guard is based on database contents, not solely file naming.
    pass
guard_database(url)
target_metadata = None


def run_migrations_offline():
    context.configure(url=url, target_metadata=None, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    engine = create_engine(url, poolclass=NullPool, connect_args={"timeout": 5})
    @event.listens_for(engine, "connect")
    def enable_sqlite_safety(connection, _record):
        cur = connection.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA busy_timeout=5000")
        cur.execute("PRAGMA journal_mode=WAL")
        cur.close()
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
