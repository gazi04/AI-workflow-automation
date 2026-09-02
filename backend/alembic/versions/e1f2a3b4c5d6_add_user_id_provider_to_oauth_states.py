"""add user_id and provider to oauth_states

Revision ID: e1f2a3b4c5d6
Revises: d2efb512a727
Create Date: 2026-08-30 00:00:00.000000

A Slack connect runs for an already-authenticated user, so the state row has to
carry who started the flow and which provider it targets. The Google flow leaves
both NULL — its callback re-derives identity from the verified Google ID token.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, Sequence[str], None] = "d2efb512a727"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "oauth_states",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "oauth_states",
        sa.Column("provider", sa.String(length=50), nullable=True),
    )
    op.create_foreign_key(
        "fk_oauth_states_user_id_users",
        "oauth_states",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "fk_oauth_states_user_id_users", "oauth_states", type_="foreignkey"
    )
    op.drop_column("oauth_states", "provider")
    op.drop_column("oauth_states", "user_id")
