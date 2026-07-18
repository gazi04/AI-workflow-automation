from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from workflow.schemas import WorkflowSchema
from workflow.services.workflow_service import WorkflowService


def _schema(trigger_type: str) -> WorkflowSchema:
    trigger_config = (
        {"type": "webhook", "config": {}}
        if trigger_type == "webhook"
        else {"type": "manual", "config": {}}
    )
    return WorkflowSchema.model_validate(
        {
            "name": "WF",
            "description": "",
            "execution_config": {
                "start_node_ids": ["t1"],
                "nodes": {
                    "t1": {"id": "t1", "type": "trigger", "config": trigger_config},
                    "a1": {
                        "id": "a1",
                        "type": "action",
                        "config": {
                            "type": "send_email",
                            "config": {
                                "to": "x@example.com",
                                "subject": "s",
                                "body": "b",
                            },
                        },
                    },
                },
                "edges": [{"id": "e1", "source": "t1", "target": "a1"}],
            },
        }
    )


def test_schema_has_webhook_trigger_true():
    assert WorkflowService.schema_has_webhook_trigger(_schema("webhook")) is True


def test_schema_has_webhook_trigger_false():
    assert WorkflowService.schema_has_webhook_trigger(_schema("manual")) is False


def test_generate_webhook_secret_is_random_and_nonempty():
    s1 = WorkflowService.generate_webhook_secret()
    s2 = WorkflowService.generate_webhook_secret()
    assert s1 and s2 and s1 != s2


async def test_create_stores_webhook_secret():
    db = AsyncMock()
    captured = {}

    def _add(obj):
        captured["wf"] = obj

    # `AsyncSession.add` is a plain sync method, so it must stay a MagicMock
    # even though the rest of `db` is an AsyncMock.
    db.add = MagicMock(side_effect=_add)

    await WorkflowService.create(
        db,
        workflow_id=uuid4(),
        user_id=uuid4(),
        schema=_schema("webhook"),
        webhook_secret="abc123",
    )
    assert captured["wf"].webhook_secret == "abc123"


async def test_update_config_backfills_secret_when_webhook_added():
    workflow = MagicMock()
    workflow.webhook_secret = None  # no secret yet
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = workflow
    db.execute = AsyncMock(return_value=mock_result)

    await WorkflowService.update_config(db, uuid4(), _schema("webhook"))

    assert workflow.webhook_secret  # a secret was generated


async def test_update_config_no_secret_for_non_webhook():
    workflow = MagicMock()
    workflow.webhook_secret = None
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = workflow
    db.execute = AsyncMock(return_value=mock_result)

    await WorkflowService.update_config(db, uuid4(), _schema("manual"))

    assert workflow.webhook_secret is None
