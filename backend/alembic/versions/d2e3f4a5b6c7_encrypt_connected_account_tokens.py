"""encrypt connected_account oauth tokens in place

Google access_token / refresh_token are now Fernet-encrypted at rest
(core.crypto). Encrypt any existing plaintext values in place so connected
accounts keep working without a reconnect. Columns are already Text, so the
longer ciphertext fits; no schema change.

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-06-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from core.crypto import encrypt_token


# revision identifiers, used by Alembic.
revision: str = 'd2e3f4a5b6c7'
down_revision: Union[str, Sequence[str], None] = 'c1d2e3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id, access_token, refresh_token FROM connected_accounts")
    ).fetchall()
    for row_id, access_token, refresh_token in rows:
        conn.execute(
            sa.text(
                "UPDATE connected_accounts "
                "SET access_token = :at, refresh_token = :rt WHERE id = :id"
            ),
            {
                "at": encrypt_token(access_token),
                "rt": encrypt_token(refresh_token),
                "id": row_id,
            },
        )


def downgrade() -> None:
    from core.crypto import decrypt_token

    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id, access_token, refresh_token FROM connected_accounts")
    ).fetchall()
    for row_id, access_token, refresh_token in rows:
        conn.execute(
            sa.text(
                "UPDATE connected_accounts "
                "SET access_token = :at, refresh_token = :rt WHERE id = :id"
            ),
            {
                "at": decrypt_token(access_token),
                "rt": decrypt_token(refresh_token),
                "id": row_id,
            },
        )
