"""update status column of workflow tables

Revision ID: 9116db711990
Revises: cfdab8a922ec
Create Date: 2025-12-22 17:15:25.222694

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9116db711990'
down_revision: Union[str, Sequence[str], None] = 'cfdab8a922ec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
