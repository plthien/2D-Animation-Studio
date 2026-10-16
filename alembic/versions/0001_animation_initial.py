"""Initial animation-only schema; independent of YTB migration lineage."""
from pathlib import Path

from alembic import op

revision = "0001_animation_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    ddl_path = Path(__file__).resolve().parents[2] / "contracts/animation/animation_schema.sql"
    ddl = ddl_path.read_text(encoding="utf-8")
    for statement in ddl.split(";"):
        statement = statement.strip()
        if statement and not statement.upper().startswith("PRAGMA "):
            op.execute(statement)


def downgrade() -> None:
    raise RuntimeError("Downgrades are disabled; immutable user-owned data must not be dropped")
