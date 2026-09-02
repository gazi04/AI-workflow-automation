"""add unique (user_id, provider) to connected_accounts

Revision ID: e2f3a4b5c6d7
Revises: e1f2a3b4c5d6
Create Date: 2026-08-30 00:00:01.000000

One connected account per (user, provider) is already assumed by the read path
(`AccountService.get_account_by_user_and_provider` uses `scalar_one_or_none()`).
Enforcing it removes a latent concurrent-double-insert race, turning it into a
clean IntegrityError. A second OAuth provider (Slack) makes that race reachable.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e2f3a4b5c6d7"
down_revision: Union[str, Sequence[str], None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CONSTRAINT = "uq_connected_accounts_user_provider"


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    dupes = bind.execute(
        sa.text(
            "SELECT user_id, provider, count(*) AS c FROM connected_accounts "
            "GROUP BY user_id, provider HAVING count(*) > 1"
        )
    ).fetchall()
    if dupes:
        raise RuntimeError(
            "connected_accounts has duplicate (user_id, provider) rows; resolve "
            f"them before adding {_CONSTRAINT}: {[tuple(r) for r in dupes]}"
        )

    op.create_unique_constraint(
        _CONSTRAINT, "connected_accounts", ["user_id", "provider"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(_CONSTRAINT, "connected_accounts", type_="unique")
