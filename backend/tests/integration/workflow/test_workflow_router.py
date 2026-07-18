from unittest.mock import AsyncMock, patch
from uuid import uuid4


# ---------------------------------------------------------------------------
# Minimal valid WorkflowSchema JSON body
# ---------------------------------------------------------------------------

VALID_WORKFLOW = {
    "name": "Test Workflow",
    "description": "A simple test workflow",
    "execution_config": {
        "start_node_ids": ["trigger_1"],
        "nodes": {
            "trigger_1": {
                "id": "trigger_1",
                "type": "trigger",
                "config": {
                    "type": "email_received",
                    "config": {"from": None, "subject_contains": None},
                },
            },
            "action_1": {
                "id": "action_1",
                "type": "action",
                "config": {
                    "type": "send_email",
                    "config": {
                        "to": "recipient@example.com",
                        "subject": "Test Subject",
                        "body": "Hello",
                    },
                },
            },
        },
        "edges": [{"id": "e1", "source": "trigger_1", "target": "action_1"}],
    },
}

INVALID_WORKFLOW = {
    "name": "Bad Workflow",
    "description": "Missing required fields",
    "execution_config": {
        "start_node_ids": ["trigger_1"],
        "nodes": {
            "trigger_1": {
                "id": "trigger_1",
                "type": "trigger",
                "config": {
                    "type": "email_received",
                    "config": {"from": None, "subject_contains": None},
                },
            },
        },
        "edges": [],
    },
}


# ---------------------------------------------------------------------------
# GET /api/workflow/catalog — public, no auth
# ---------------------------------------------------------------------------


async def test_catalog_returns_200(client):
    response = await client.get("/api/workflow/catalog")
    assert response.status_code == 200


async def test_catalog_has_required_keys(client):
    response = await client.get("/api/workflow/catalog")
    body = response.json()
    assert "triggers" in body
    assert "actions" in body
    assert "conditions" in body


async def test_catalog_triggers_non_empty(client):
    response = await client.get("/api/workflow/catalog")
    assert len(response.json()["triggers"]) > 0


async def test_catalog_actions_non_empty(client):
    response = await client.get("/api/workflow/catalog")
    assert len(response.json()["actions"]) > 0


# ---------------------------------------------------------------------------
# GET /api/workflow/get_workflows — requires auth
# ---------------------------------------------------------------------------


async def test_get_workflows_requires_auth(client):
    response = await client.get("/api/workflow/get_workflows")
    assert response.status_code == 401


async def test_get_workflows_returns_empty_list_for_new_user(client, auth_headers):
    response = await client.get("/api/workflow/get_workflows", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []


async def test_get_workflows_only_returns_own(client, auth_headers):
    """Workflow created by this user appears in their GET list."""
    fake_id = uuid4()
    with patch(
        "workflow.routes.workflow_router.DeploymentService.create_deployment_for_workflow",
        new=AsyncMock(return_value=fake_id),
    ):
        create_resp = await client.post(
            "/api/workflow/create", json=VALID_WORKFLOW, headers=auth_headers
        )
    assert create_resp.status_code == 200
    created_id = create_resp.json()["id"]

    get_resp = await client.get("/api/workflow/get_workflows", headers=auth_headers)
    assert get_resp.status_code == 200
    workflow_ids = [w["id"] for w in get_resp.json()]
    assert created_id in workflow_ids


# ---------------------------------------------------------------------------
# POST /api/workflow/create — requires auth, calls Prefect (mocked)
# ---------------------------------------------------------------------------


async def test_create_workflow_valid(client, auth_headers):
    fake_deployment_id = uuid4()
    with patch(
        "workflow.routes.workflow_router.DeploymentService.create_deployment_for_workflow",
        new=AsyncMock(return_value=fake_deployment_id),
    ):
        response = await client.post(
            "/api/workflow/create",
            json=VALID_WORKFLOW,
            headers=auth_headers,
        )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Test Workflow"
    assert str(fake_deployment_id) == body["id"]


async def test_create_workflow_db_failure_rolls_back_orphan_deployment(
    client, auth_headers
):
    """If the DB write fails after the Prefect deployment is created, the
    orphaned deployment is deleted instead of being left to fire on schedule."""
    fake_deployment_id = uuid4()
    with (
        patch(
            "workflow.routes.workflow_router.DeploymentService.create_deployment_for_workflow",
            new=AsyncMock(return_value=fake_deployment_id),
        ),
        patch(
            "workflow.routes.workflow_router.WorkflowService.create",
            side_effect=RuntimeError("db boom"),
        ),
        patch(
            "workflow.routes.workflow_router.DeploymentService.delete",
            new=AsyncMock(return_value=None),
        ) as mock_delete,
    ):
        response = await client.post(
            "/api/workflow/create",
            json=VALID_WORKFLOW,
            headers=auth_headers,
        )

    assert response.status_code == 500
    mock_delete.assert_awaited_once_with(fake_deployment_id)


async def test_create_workflow_requires_auth(client, csrf_headers):
    response = await client.post(
        "/api/workflow/create", json=VALID_WORKFLOW, headers=csrf_headers
    )
    assert response.status_code == 401


async def test_create_workflow_invalid_schema_returns_422(client, auth_headers):
    response = await client.post(
        "/api/workflow/create",
        json=INVALID_WORKFLOW,
        headers=auth_headers,
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /api/workflow/delete — requires auth, calls Prefect (mocked)
# ---------------------------------------------------------------------------


async def test_delete_workflow(client, auth_headers):
    # First create a workflow
    fake_deployment_id = uuid4()
    with patch(
        "workflow.routes.workflow_router.DeploymentService.create_deployment_for_workflow",
        new=AsyncMock(return_value=fake_deployment_id),
    ):
        create_resp = await client.post(
            "/api/workflow/create",
            json=VALID_WORKFLOW,
            headers=auth_headers,
        )
    assert create_resp.status_code == 200

    # Now delete it
    with patch(
        "workflow.routes.workflow_router.DeploymentService.delete",
        new=AsyncMock(return_value=None),
    ):
        delete_resp = await client.delete(
            f"/api/workflow/delete?deployment_id={fake_deployment_id}",
            headers=auth_headers,
        )
    assert delete_resp.status_code == 200

    # Verify gone
    get_resp = await client.get("/api/workflow/get_workflows", headers=auth_headers)
    assert get_resp.json() == []


# ---------------------------------------------------------------------------
# Authorization / IDOR — ownership enforced per user
# ---------------------------------------------------------------------------


async def _create_workflow(client, headers) -> str:
    """Create a workflow (Prefect mocked) and return its id."""
    fake_id = uuid4()
    with patch(
        "workflow.routes.workflow_router.DeploymentService.create_deployment_for_workflow",
        new=AsyncMock(return_value=fake_id),
    ):
        resp = await client.post(
            "/api/workflow/create", json=VALID_WORKFLOW, headers=headers
        )
    assert resp.status_code == 200
    return resp.json()["id"]


async def test_get_workflow_not_found_returns_404(client, auth_headers):
    resp = await client.get(f"/api/workflow/get_workflow/{uuid4()}", headers=auth_headers)
    assert resp.status_code == 404


async def test_get_workflow_owner_succeeds(client, auth_headers):
    wid = await _create_workflow(client, auth_headers)
    resp = await client.get(f"/api/workflow/get_workflow/{wid}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == wid


async def test_get_workflow_other_user_gets_404(client, auth_headers, second_auth_headers):
    wid = await _create_workflow(client, auth_headers)
    resp = await client.get(
        f"/api/workflow/get_workflow/{wid}", headers=second_auth_headers
    )
    assert resp.status_code == 404


async def test_toggle_other_user_gets_404(client, auth_headers, second_auth_headers):
    wid = await _create_workflow(client, auth_headers)
    resp = await client.patch(
        "/api/workflow/toggle",
        json={"deployment_id": wid, "status": False},
        headers=second_auth_headers,
    )
    assert resp.status_code == 404


async def test_toggle_requires_auth(client, csrf_headers):
    resp = await client.patch(
        "/api/workflow/toggle",
        json={"deployment_id": str(uuid4()), "status": False},
        headers=csrf_headers,
    )
    assert resp.status_code == 401


async def test_update_config_other_user_gets_404(client, auth_headers, second_auth_headers):
    wid = await _create_workflow(client, auth_headers)
    resp = await client.patch(
        "/api/workflow/update-config",
        json={"deployment_id": wid, "schema": VALID_WORKFLOW},
        headers=second_auth_headers,
    )
    assert resp.status_code == 404


async def test_delete_other_user_gets_404(client, auth_headers, second_auth_headers):
    wid = await _create_workflow(client, auth_headers)
    resp = await client.delete(
        f"/api/workflow/delete?deployment_id={wid}", headers=second_auth_headers
    )
    assert resp.status_code == 404


async def test_run_other_user_gets_404(client, auth_headers, second_auth_headers):
    wid = await _create_workflow(client, auth_headers)
    resp = await client.post(
        "/api/workflow/run",
        json={"deployment_id": wid},
        headers=second_auth_headers,
    )
    assert resp.status_code == 404


async def test_run_requires_auth(client, csrf_headers):
    resp = await client.post(
        "/api/workflow/run",
        json={"deployment_id": str(uuid4())},
        headers=csrf_headers,
    )
    assert resp.status_code == 401


async def test_history_other_user_gets_404(client, auth_headers, second_auth_headers):
    wid = await _create_workflow(client, auth_headers)
    resp = await client.get(f"/api/workflow/{wid}/history", headers=second_auth_headers)
    assert resp.status_code == 404


async def test_history_owner_succeeds(client, auth_headers):
    wid = await _create_workflow(client, auth_headers)
    with patch(
        "workflow.routes.workflow_router.DeploymentService.get_workflow_history",
        new=AsyncMock(return_value=[]),
    ):
        resp = await client.get(f"/api/workflow/{wid}/history", headers=auth_headers)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /api/workflow/{id}/export — requires auth + ownership
# ---------------------------------------------------------------------------


async def test_export_workflow_owner_succeeds(client, auth_headers):
    wid = await _create_workflow(client, auth_headers)
    resp = await client.get(f"/api/workflow/{wid}/export", headers=auth_headers)
    assert resp.status_code == 200
    assert "attachment" in resp.headers["content-disposition"]
    body = resp.json()
    assert body["name"] == "Test Workflow"
    assert body["execution_config"]["nodes"].keys() == {"trigger_1", "action_1"}


async def test_export_workflow_other_user_gets_404(client, auth_headers, second_auth_headers):
    wid = await _create_workflow(client, auth_headers)
    resp = await client.get(f"/api/workflow/{wid}/export", headers=second_auth_headers)
    assert resp.status_code == 404


async def test_export_workflow_requires_auth(client):
    resp = await client.get(f"/api/workflow/{uuid4()}/export")
    assert resp.status_code == 401


async def test_run_logs_rejects_non_owner(client, auth_headers):
    with patch(
        "workflow.routes.workflow_router.DeploymentService.user_owns_run",
        new=AsyncMock(return_value=False),
    ):
        resp = await client.get(f"/api/workflow/runs/{uuid4()}/logs", headers=auth_headers)
    assert resp.status_code == 404


async def test_run_logs_owner_succeeds(client, auth_headers):
    with (
        patch(
            "workflow.routes.workflow_router.DeploymentService.user_owns_run",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "workflow.routes.workflow_router.DeploymentService.get_run_logs",
            new=AsyncMock(return_value=[]),
        ),
    ):
        resp = await client.get(f"/api/workflow/runs/{uuid4()}/logs", headers=auth_headers)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# WebSocket auth — token required, must match path user_id
# ---------------------------------------------------------------------------


def test_ws_rejects_missing_token():
    # httpx.AsyncClient (the `client` fixture) has no websocket_connect
    # support, so — matching tests/test_websocket.py — use the sync
    # fastapi.testclient.TestClient directly for websocket tests.
    from fastapi.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect
    import pytest

    from main import app

    ws_client = TestClient(app)
    with pytest.raises(WebSocketDisconnect):
        with ws_client.websocket_connect(f"/api/workflow/ws/workflows/{uuid4()}"):
            pass


async def test_ws_rejects_mismatched_user(test_user):
    from fastapi.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect
    from auth.utils import create_access_token
    import pytest

    from main import app

    token = create_access_token({"sub": str(test_user.id), "email": test_user.email})
    other_id = uuid4()  # path id different from token sub
    ws_client = TestClient(app)
    with pytest.raises(WebSocketDisconnect):
        with ws_client.websocket_connect(
            f"/api/workflow/ws/workflows/{other_id}?token={token}"
        ):
            pass


# ---------------------------------------------------------------------------
# GET /api/workflow/runs/{run_id}/audit — persisted per-node execution audit
# ---------------------------------------------------------------------------


async def _create_run_record(db_session, user, *, prefect_run_id):
    """Persist a workflow + audit record owned by `user`; returns the record."""
    from workflow.models.workflow import Workflow
    from workflow.services import WorkflowRunService

    workflow = Workflow(
        id=uuid4(),
        user_id=user.id,
        name="WF",
        description="d",
        is_active=True,
        config={},
    )
    db_session.add(workflow)
    await db_session.flush()
    return await WorkflowRunService.create(
        db_session,
        workflow_id=workflow.id,
        user_id=user.id,
        node_results={
            "node_1": {"output": {"x": 1}, "status": "success", "error": None}
        },
        status="success",
        prefect_run_id=prefect_run_id,
        trigger_data={"from": "a@b.com"},
        duration_ms=120,
    )


async def test_run_audit_owner_succeeds(client, db_session, test_user, auth_headers):
    prefect_run_id = uuid4()
    await _create_run_record(db_session, test_user, prefect_run_id=prefect_run_id)

    resp = await client.get(
        f"/api/workflow/runs/{prefect_run_id}/audit", headers=auth_headers
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert body["duration_ms"] == 120
    assert body["trigger_data"] == {"from": "a@b.com"}
    assert body["node_results"]["node_1"]["output"] == {"x": 1}
    assert body["node_results"]["node_1"]["status"] == "success"


async def test_run_audit_unknown_run_returns_404(client, auth_headers):
    resp = await client.get(f"/api/workflow/runs/{uuid4()}/audit", headers=auth_headers)
    assert resp.status_code == 404


async def test_run_audit_other_user_returns_404(
    client, db_session, second_user, auth_headers
):
    # Record owned by second_user; test_user (auth_headers) must not see it.
    prefect_run_id = uuid4()
    await _create_run_record(db_session, second_user, prefect_run_id=prefect_run_id)

    resp = await client.get(
        f"/api/workflow/runs/{prefect_run_id}/audit", headers=auth_headers
    )

    assert resp.status_code == 404


async def test_run_audit_requires_auth(client):
    resp = await client.get(f"/api/workflow/runs/{uuid4()}/audit")
    assert resp.status_code == 401
