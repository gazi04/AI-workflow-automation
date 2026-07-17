"""add processed_messages workflow fk

`processed_messages.workflow_id` had no foreign key, so deleting a workflow left
its dedup rows behind: WorkflowService.delete_by_id issues a Core DELETE, which
bypasses ORM-level cascades — only a DB-level ON DELETE CASCADE cleans up here.
Mirrors workflow_runs.workflow_id, which already has the same FK + index.

Revision ID: f4a5b6c7d8e9
Revises: e3f4a5b6c7d8
Create Date: 2026-07-17 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f4a5b6c7d8e9"
down_revision: Union[str, Sequence[str], None] = "e3f4a5b6c7d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Workflows deleted before this FK existed left their dedup rows behind.
    # The rows are unreachable — lookups are by (message_id, workflow_id) and
    # that workflow_id no longer exists — and the FK cannot be added while they
    # are present, so drop them first.
    op.execute(
        "DELETE FROM processed_messages pm "
        "WHERE NOT EXISTS (SELECT 1 FROM workflows w WHERE w.id = pm.workflow_id)"
    )
    # Postgres does not auto-index FK columns, and uq_message_workflow_pair
    # (message_id, workflow_id) cannot serve a workflow_id-alone lookup, so the
    # cascade would seq-scan without this.
    op.create_index(
        "ix_processed_messages_workflow_id", "processed_messages", ["workflow_id"]
    )
    op.create_foreign_key(
        "processed_messages_workflow_id_fkey",
        "processed_messages",
        "workflows",
        ["workflow_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "processed_messages_workflow_id_fkey", "processed_messages", type_="foreignkey"
    )
    op.drop_index("ix_processed_messages_workflow_id", table_name="processed_messages")
    # Orphan rows deleted in upgrade() are not restored — they were unreachable.
