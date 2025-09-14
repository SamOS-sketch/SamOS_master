"""A8b: images provenance + drift

- Add columns to `images`:
  ref_used (BOOL, default false, non-null)
  drift_score (FLOAT, nullable)
  provider (TEXT, default 'stub', non-null)
  tier (TEXT, nullable)
  latency_ms (INTEGER, nullable)
  status (TEXT, default 'ok', non-null)
  meta_json (TEXT, nullable)
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "e67264c84611"
down_revision = None          # this is the first/baseline migration
branch_labels = None
depends_on = None


def upgrade():
    # Use batch mode for SQLite compatibility
    with op.batch_alter_table("images") as batch:
        # Add columns if they don't already exist.
        # SQLite doesn't support IF NOT EXISTS for columns, so we try/ignore.
        try:
            batch.add_column(sa.Column("ref_used", sa.Boolean(), nullable=False, server_default=sa.text("0")))
        except Exception:
            pass
        try:
            batch.add_column(sa.Column("drift_score", sa.Float(), nullable=True))
        except Exception:
            pass
        try:
            batch.add_column(sa.Column("provider", sa.String(), nullable=False, server_default="stub"))
        except Exception:
            pass
        try:
            batch.add_column(sa.Column("tier", sa.String(), nullable=True))
        except Exception:
            pass
        try:
            batch.add_column(sa.Column("latency_ms", sa.Integer(), nullable=True))
        except Exception:
            pass
        try:
            batch.add_column(sa.Column("status", sa.String(), nullable=False, server_default="ok"))
        except Exception:
            pass
        try:
            batch.add_column(sa.Column("meta_json", sa.Text(), nullable=True))
        except Exception:
            pass

    # Clean up server defaults after backfill so app-side defaults apply
    with op.batch_alter_table("images") as batch:
        try:
            batch.alter_column("ref_used", server_default=None)
        except Exception:
            pass
        try:
            batch.alter_column("provider", server_default=None)
        except Exception:
            pass
        try:
            batch.alter_column("status", server_default=None)
        except Exception:
            pass


def downgrade():
    with op.batch_alter_table("images") as batch:
        for col in ("meta_json", "status", "latency_ms", "tier", "provider", "drift_score", "ref_used"):
            try:
                batch.drop_column(col)
            except Exception:
                pass
