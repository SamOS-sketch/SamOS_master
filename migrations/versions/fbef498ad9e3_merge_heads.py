"""merge heads

Revision ID: fbef498ad9e3
Revises: 650f75e3e89f, 6f0e539892f0
Create Date: 2026-01-26 18:10:09.809740

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fbef498ad9e3'
down_revision: Union[str, Sequence[str], None] = ('650f75e3e89f', '6f0e539892f0')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
