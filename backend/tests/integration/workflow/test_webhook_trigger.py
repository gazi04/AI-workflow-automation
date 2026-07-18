"""Integration tests for the generic HTTP webhook trigger endpoint
(POST /api/webhooks/trigger/{workflow_id})."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from workflow.models.workflow import Workflow


SECRET = "super-secret-token"


def _action_node():
    return {
        "a1": {
            "id": "a1",
            "type": "action",
            "config": {
                "type": "send_email",
                "config": {"to": "x@example.com", "subject": "s", "body": "b"},
            },
        },
    }


def _config_with_trigger(trigger_config):
    """A valid execution config: one start trigger wired to one action."""
    return {
        "start_node_ids": ["trigger_1"],
        "nodes": {
            "trigger_1": {
                "id": "trigger_1",
                "type": "trigger",
                "config": trigger_config,
            },
            **_action_node(),
        },
        "edges": [{"id": "e1", "source": "trigger_1", "target": "a1"}],
    }


def _webhook_config():
    return _config_with_trigger(
        {"type": "webhook", "config": {"description": "Triggered by an HTTP request"}}
    )


def _email_config():
    return _config_with_trigger(
        {"type": "email_received", "config": {"from": None, "subject_contains": None}}
    )


@pytest.fixture
async def webhook_workflow(db_session, test_user):
    wf = Workflow(
        id=uuid4(),
        user_id=test_user.id,
        name="Webhook WF",
        description="",
        config=_webhook_config(),
        ui_metadata={},
        is_active=True,
        webhook_secret=SECRET,
    )
    db_session.add(wf)
    await db_session.flush()
    return wf


@pytest.fixture
def _run_mock():
    with patch(
        "gmail.routes.webhook_router.DeploymentService.run",
        new=AsyncMock(return_value=None),
    ) as m:
        yield m


async def test_valid_secret_triggers_run(client, webhook_workflow, _run_mock):
    resp = await client.post(
        f"/api/webhooks/trigger/{webhook_workflow.id}",
        headers={"X-Webhook-Secret": SECRET},
        json={"hello": "world"},
    )
    assert resp.status_code == 202
    _run_mock.assert_awaited_once()
    args, _ = _run_mock.await_args
    assert args[0] == webhook_workflow.id
    ctx = args[1]["trigger_context"]
    assert ctx["matched_trigger_node_id"] == "trigger_1"
    assert ctx["webhook_payload"]["body"] == {"hello": "world"}


async def test_secret_via_query_param(client, webhook_workflow, _run_mock):
    resp = await client.post(
        f"/api/webhooks/trigger/{webhook_workflow.id}?secret={SECRET}",
        json={},
    )
    assert resp.status_code == 202
    _run_mock.assert_awaited_once()


async def test_wrong_secret_rejected(client, webhook_workflow, _run_mock):
    resp = await client.post(
        f"/api/webhooks/trigger/{webhook_workflow.id}",
        headers={"X-Webhook-Secret": "nope"},
        json={},
    )
    assert resp.status_code == 401
    _run_mock.assert_not_awaited()


async def test_missing_secret_rejected(client, webhook_workflow, _run_mock):
    resp = await client.post(f"/api/webhooks/trigger/{webhook_workflow.id}", json={})
    assert resp.status_code == 401
    _run_mock.assert_not_awaited()


async def test_unknown_workflow_404(client, _run_mock):
    resp = await client.post(
        f"/api/webhooks/trigger/{uuid4()}",
        headers={"X-Webhook-Secret": SECRET},
        json={},
    )
    assert resp.status_code == 404
    _run_mock.assert_not_awaited()


async def test_inactive_workflow_404(client, db_session, webhook_workflow, _run_mock):
    webhook_workflow.is_active = False
    await db_session.flush()
    resp = await client.post(
        f"/api/webhooks/trigger/{webhook_workflow.id}",
        headers={"X-Webhook-Secret": SECRET},
        json={},
    )
    assert resp.status_code == 404
    _run_mock.assert_not_awaited()


async def test_non_webhook_workflow_404(client, db_session, test_user, _run_mock):
    """A workflow with a secret but no webhook trigger node must not be triggerable."""
    wf = Workflow(
        id=uuid4(),
        user_id=test_user.id,
        name="Email WF",
        description="",
        config=_email_config(),
        ui_metadata={},
        is_active=True,
        webhook_secret=SECRET,
    )
    db_session.add(wf)
    await db_session.flush()

    resp = await client.post(
        f"/api/webhooks/trigger/{wf.id}",
        headers={"X-Webhook-Secret": SECRET},
        json={},
    )
    assert resp.status_code == 404
    _run_mock.assert_not_awaited()
