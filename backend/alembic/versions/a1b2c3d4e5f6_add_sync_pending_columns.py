"""add sync_pending and latest_observed_history_id to connected_accounts

Revision ID: a1b2c3d4e5f6
Revises: 870088582def
Create Date: 2026-06-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '870088582def'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "connected_accounts",
        sa.Column(
            "sync_pending",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "connected_accounts",
        sa.Column("latest_observed_history_id", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("connected_accounts", "latest_observed_history_id")
    op.drop_column("connected_accounts", "sync_pending")
