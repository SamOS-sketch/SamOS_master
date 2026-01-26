"""add local_path to images

Revision ID: 650f75e3e89f
Revises: 26d246f7358a
Create Date: 2026-01-26
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "650f75e3e89f"
down_revision = "26d246f7358a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("images", sa.Column("local_path", sa.Text(), nullable=True))


def downgrade() -> None:
    # SQLite downgrade for DROP COLUMN is non-trivial (table rebuild).
    # Keep as no-op for safety in dev.
    pass
