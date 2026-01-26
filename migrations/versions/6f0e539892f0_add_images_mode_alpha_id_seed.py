"""add images mode alpha_id seed

Revision ID: 6f0e539892f0
Revises: 26d246f7358a
Create Date: <AUTO>

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "6f0e539892f0"
down_revision = "26d246f7358a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("images", sa.Column("mode", sa.String(), nullable=True))
    op.add_column("images", sa.Column("alpha_id", sa.String(), nullable=True))
    op.add_column("images", sa.Column("seed", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("images", "seed")
    op.drop_column("images", "alpha_id")
    op.drop_column("images", "mode")