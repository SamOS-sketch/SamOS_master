"""A8b: images provenance + drift

Revision ID: 26d246f7358a
Revises: 2a99e8b569fa
Create Date: 2025-09-12 14:32:43.320676
"""

from alembic import op
import sqlalchemy as sa


# --- Alembic identifiers ---
revision = "26d246f7358a"
down_revision = "2a99e8b569fa"   # must point to the core tables migration
branch_labels = None
depends_on = None


def _has_column(bind, table: str, column: str) -> bool:
    insp = sa.inspect(bind)
    return any(col["name"] == column for col in insp.get_columns(table))


def _add_col_if_missing(table: str, name: str, col: sa.Column):
    """
    SQLite-safe helper: only add the column if it's not present.
    Uses batch_alter_table so Alembic can recreate the table when needed.
    """
    bind = op.get_bind()
    if not _has_column(bind, table, name):
        with op.batch_alter_table(table) as batch:
            batch.add_column(col)


def upgrade() -> None:
    """
    Add A8b fields to `images` if they do not already exist.

    Fields:
      - ref_used       (BOOLEAN, default False)
      - drift_score    (FLOAT, nullable)
      - provider       (TEXT, nullable)
      - tier           (TEXT, nullable)
      - latency_ms     (INTEGER, nullable)
      - provenance     (TEXT, nullable)
      - status         (TEXT, default "ok")
      - meta_json      (TEXT, nullable)
    """
    # NOTE: For SQLite, avoid NOT NULL without a server_default on ADD COLUMN.
    _add_col_if_missing(
        "images",
        "ref_used",
        sa.Column("ref_used", sa.Boolean(), nullable=True, server_default=sa.text("0")),
    )
    _add_col_if_missing(
        "images",
        "drift_score",
        sa.Column("drift_score", sa.Float(), nullable=True),
    )
    _add_col_if_missing(
        "images",
        "provider",
        sa.Column("provider", sa.String(length=64), nullable=True),
    )
    _add_col_if_missing(
        "images",
        "tier",
        sa.Column("tier", sa.String(length=32), nullable=True),
    )
    _add_col_if_missing(
        "images",
        "latency_ms",
        sa.Column("latency_ms", sa.Integer(), nullable=True),
    )
    _add_col_if_missing(
        "images",
        "provenance",
        sa.Column("provenance", sa.Text(), nullable=True),
    )
    _add_col_if_missing(
        "images",
        "status",
        sa.Column("status", sa.String(), nullable=True, server_default=sa.text("'ok'")),
    )
    _add_col_if_missing(
        "images",
        "meta_json",
        sa.Column("meta_json", sa.Text(), nullable=True),
    )
    # If your earlier schema lacked created_at on images, add it too (safe no-op if present)
    _add_col_if_missing(
        "images",
        "created_at",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    """
    Drop the A8b fields from `images` (if present), using batch mode for SQLite.
    """
    bind = op.get_bind()
    to_drop = [
        "meta_json",
        "status",
        "provenance",
        "latency_ms",
        "tier",
        "provider",
        "drift_score",
        "ref_used",
        # Only drop created_at if we created it here (safe to keep this guard):
        "created_at",
    ]

    existing = {c["name"] for c in sa.inspect(bind).get_columns("images")}
    cols = [c for c in to_drop if c in existing]
    if not cols:
        return

    with op.batch_alter_table("images") as batch:
        for c in cols:
            batch.drop_column(c)
