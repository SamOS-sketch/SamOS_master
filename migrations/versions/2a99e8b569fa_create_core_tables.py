"""create core tables (SQLite-safe)

Revision ID: 2a99e8b569fa
Revises: e67264c84611
Create Date: 2025-09-12 00:00:00
"""

from alembic import op
import sqlalchemy as sa

# --- Alembic identifiers ---
revision = "2a99e8b569fa"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the core tables (sessions, images, events, memories, emms)."""

    # sessions table
    op.create_table(
        "sessions",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("mode", sa.String, nullable=False),
        sa.Column("persona", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # images table
    op.create_table(
        "images",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("session_id", sa.String, sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("url", sa.String, nullable=True),  # leave nullable for SQLite safety
        sa.Column("prompt", sa.Text, nullable=True),
        sa.Column("ref_used", sa.Boolean, default=False),
        sa.Column("drift_score", sa.Float, nullable=True),
        sa.Column("provider", sa.String, nullable=True),
        sa.Column("tier", sa.String, nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("provenance", sa.Text, nullable=True),
        sa.Column("status", sa.String, default="ok"),
        sa.Column("meta_json", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # events table
    op.create_table(
        "events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String, sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("kind", sa.String, nullable=False),
        sa.Column("message", sa.Text, nullable=True),
        sa.Column("meta", sa.Text, nullable=True),
    )

    # memories table
    op.create_table(
        "memories",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("session_id", sa.String, sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # emms table
    op.create_table(
        "emms",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String, sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("tag", sa.String, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    """Drop all core tables in reverse order to satisfy FKs."""
    op.drop_table("emms")
    op.drop_table("memories")
    op.drop_table("events")
    op.drop_table("images")
    op.drop_table("sessions")
