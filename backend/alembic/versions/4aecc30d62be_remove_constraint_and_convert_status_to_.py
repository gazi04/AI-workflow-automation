"""remove constraint and convert status to boolean

Revision ID: 4aecc30d62be
Revises: 9116db711990
Create Date: 2025-12-22 17:45:34.610377

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4aecc30d62be'
down_revision: Union[str, Sequence[str], None] = '9116db711990'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint('workflows_status_check', 'workflows', type_='check')
    op.alter_column('workflows', 'status',
               existing_type=sa.VARCHAR(length=20),
               type_=sa.Boolean(),
               existing_nullable=False,
               postgresql_using="CASE WHEN status = 'active' THEN TRUE ELSE FALSE END")


def downgrade() -> None:
    """Downgrade schema."""
    # Reverse the process
    op.alter_column('workflows', 'status',
               existing_type=sa.Boolean(),
               type_=sa.VARCHAR(length=20),
               existing_nullable=False,
               postgresql_using="CASE WHEN status THEN 'active' ELSE 'inactive' END")
    
    # Re-add the constraint
    op.create_check_constraint(
        'workflows_status_check',
        'workflows',
        "status IN ('active', 'inactive', 'paused', 'failed')"
    )
