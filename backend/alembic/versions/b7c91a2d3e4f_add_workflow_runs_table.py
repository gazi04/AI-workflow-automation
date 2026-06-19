"""add workflow_runs table

Revision ID: b7c91a2d3e4f
Revises: 433ce5d966d4
Create Date: 2026-06-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b7c91a2d3e4f'
down_revision: Union[str, Sequence[str], None] = '433ce5d966d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'workflow_runs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('workflow_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('prefect_run_id', sa.UUID(), nullable=True),
        sa.Column('trigger_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('node_results', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('failure_notified', sa.Boolean(), nullable=False),
        sa.Column('triggered_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['workflow_id'], ['workflows.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_workflow_runs_workflow_id'), 'workflow_runs', ['workflow_id'], unique=False
    )
    op.create_index(
        op.f('ix_workflow_runs_user_id'), 'workflow_runs', ['user_id'], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_workflow_runs_user_id'), table_name='workflow_runs')
    op.drop_index(op.f('ix_workflow_runs_workflow_id'), table_name='workflow_runs')
    op.drop_table('workflow_runs')
