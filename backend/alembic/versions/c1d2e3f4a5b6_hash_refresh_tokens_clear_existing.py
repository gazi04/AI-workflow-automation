"""hash refresh tokens: clear existing plaintext rows

Refresh tokens are now stored as SHA-256 hashes (auth.utils.hash_refresh_token).
Existing rows hold plaintext tokens that can't be reversed into hashes, so they
would never match the hashed lookup again. Delete them; affected users simply
re-login once. No schema change (the 64-char hex digest fits String(255)).

Revision ID: c1d2e3f4a5b6
Revises: b7c91a2d3e4f
Create Date: 2026-06-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, Sequence[str], None] = 'b7c91a2d3e4f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DELETE FROM refresh_tokens")


def downgrade() -> None:
    # Irreversible: the original plaintext tokens are gone.
    pass
