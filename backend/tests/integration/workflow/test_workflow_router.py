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


def test_catalog_returns_200(client):
    response = client.get("/api/workflow/catalog")
    assert response.status_code == 200


def test_catalog_has_required_keys(client):
    response = client.get("/api/workflow/catalog")
    body = response.json()
    assert "triggers" in body
    assert "actions" in body
    assert "conditions" in body


def test_catalog_triggers_non_empty(client):
    response = client.get("/api/workflow/catalog")
    assert len(response.json()["triggers"]) > 0


def test_catalog_actions_non_empty(client):
    response = client.get("/api/workflow/catalog")
    assert len(response.json()["actions"]) > 0


# ---------------------------------------------------------------------------
# GET /api/workflow/get_workflows — requires auth
# ---------------------------------------------------------------------------


def test_get_workflows_requires_auth(client):
    response = client.get("/api/workflow/get_workflows")
    assert response.status_code == 401


def test_get_workflows_returns_empty_list_for_new_user(client, auth_headers):
    response = client.get("/api/workflow/get_workflows", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []


def test_get_workflows_only_returns_own(client, auth_headers):
    """Workflow created by this user appears in their GET list."""
    fake_id = uuid4()
    with patch(
        "workflow.routes.workflow_router.DeploymentService.create_deployment_for_workflow",
        new=AsyncMock(return_value=fake_id),
    ):
        create_resp = client.post(
            "/api/workflow/create", json=VALID_WORKFLOW, headers=auth_headers
        )
    assert create_resp.status_code == 200
    created_id = create_resp.json()["id"]

    get_resp = client.get("/api/workflow/get_workflows", headers=auth_headers)
    assert get_resp.status_code == 200
    workflow_ids = [w["id"] for w in get_resp.json()]
    assert created_id in workflow_ids


# ---------------------------------------------------------------------------
# POST /api/workflow/create — requires auth, calls Prefect (mocked)
# ---------------------------------------------------------------------------


def test_create_workflow_valid(client, auth_headers):
    fake_deployment_id = uuid4()
    with patch(
        "workflow.routes.workflow_router.DeploymentService.create_deployment_for_workflow",
        new=AsyncMock(return_value=fake_deployment_id),
    ):
        response = client.post(
            "/api/workflow/create",
            json=VALID_WORKFLOW,
            headers=auth_headers,
        )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Test Workflow"
    assert str(fake_deployment_id) == body["id"]


def test_create_workflow_requires_auth(client):
    response = client.post("/api/workflow/create", json=VALID_WORKFLOW)
    assert response.status_code == 401


def test_create_workflow_invalid_schema_returns_422(client, auth_headers):
    response = client.post(
        "/api/workflow/create",
        json=INVALID_WORKFLOW,
        headers=auth_headers,
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /api/workflow/delete — requires auth, calls Prefect (mocked)
# ---------------------------------------------------------------------------


def test_delete_workflow(client, auth_headers):
    # First create a workflow
    fake_deployment_id = uuid4()
    with patch(
        "workflow.routes.workflow_router.DeploymentService.create_deployment_for_workflow",
        new=AsyncMock(return_value=fake_deployment_id),
    ):
        create_resp = client.post(
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
        delete_resp = client.delete(
            f"/api/workflow/delete?deployment_id={fake_deployment_id}",
            headers=auth_headers,
        )
    assert delete_resp.status_code == 200

    # Verify gone
    get_resp = client.get("/api/workflow/get_workflows", headers=auth_headers)
    assert get_resp.json() == []


# ---------------------------------------------------------------------------
# Authorization / IDOR — ownership enforced per user
# ---------------------------------------------------------------------------


def _create_workflow(client, headers) -> str:
    """Create a workflow (Prefect mocked) and return its id."""
    fake_id = uuid4()
    with patch(
        "workflow.routes.workflow_router.DeploymentService.create_deployment_for_workflow",
        new=AsyncMock(return_value=fake_id),
    ):
        resp = client.post("/api/workflow/create", json=VALID_WORKFLOW, headers=headers)
    assert resp.status_code == 200
    return resp.json()["id"]


def test_get_workflow_not_found_returns_404(client, auth_headers):
    resp = client.get(f"/api/workflow/get_workflow/{uuid4()}", headers=auth_headers)
    assert resp.status_code == 404


def test_get_workflow_owner_succeeds(client, auth_headers):
    wid = _create_workflow(client, auth_headers)
    resp = client.get(f"/api/workflow/get_workflow/{wid}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == wid


def test_get_workflow_other_user_gets_404(client, auth_headers, second_auth_headers):
    wid = _create_workflow(client, auth_headers)
    resp = client.get(f"/api/workflow/get_workflow/{wid}", headers=second_auth_headers)
    assert resp.status_code == 404


def test_toggle_other_user_gets_404(client, auth_headers, second_auth_headers):
    wid = _create_workflow(client, auth_headers)
    resp = client.patch(
        "/api/workflow/toggle",
        json={"deployment_id": wid, "status": False},
        headers=second_auth_headers,
    )
    assert resp.status_code == 404


def test_toggle_requires_auth(client):
    resp = client.patch(
        "/api/workflow/toggle", json={"deployment_id": str(uuid4()), "status": False}
    )
    assert resp.status_code == 401


def test_update_config_other_user_gets_404(client, auth_headers, second_auth_headers):
    wid = _create_workflow(client, auth_headers)
    resp = client.patch(
        "/api/workflow/update-config",
        json={"deployment_id": wid, "schema": VALID_WORKFLOW},
        headers=second_auth_headers,
    )
    assert resp.status_code == 404


def test_delete_other_user_gets_404(client, auth_headers, second_auth_headers):
    wid = _create_workflow(client, auth_headers)
    resp = client.delete(
        f"/api/workflow/delete?deployment_id={wid}", headers=second_auth_headers
    )
    assert resp.status_code == 404


def test_run_other_user_gets_404(client, auth_headers, second_auth_headers):
    wid = _create_workflow(client, auth_headers)
    resp = client.post(
        "/api/workflow/run",
        json={"deployment_id": wid},
        headers=second_auth_headers,
    )
    assert resp.status_code == 404


def test_run_requires_auth(client):
    resp = client.post("/api/workflow/run", json={"deployment_id": str(uuid4())})
    assert resp.status_code == 401


def test_history_other_user_gets_404(client, auth_headers, second_auth_headers):
    wid = _create_workflow(client, auth_headers)
    resp = client.get(f"/api/workflow/{wid}/history", headers=second_auth_headers)
    assert resp.status_code == 404


def test_history_owner_succeeds(client, auth_headers):
    wid = _create_workflow(client, auth_headers)
    with patch(
        "workflow.routes.workflow_router.DeploymentService.get_workflow_history",
        new=AsyncMock(return_value=[]),
    ):
        resp = client.get(f"/api/workflow/{wid}/history", headers=auth_headers)
    assert resp.status_code == 200


def test_run_logs_rejects_non_owner(client, auth_headers):
    with patch(
        "workflow.routes.workflow_router.DeploymentService.user_owns_run",
        new=AsyncMock(return_value=False),
    ):
        resp = client.get(f"/api/workflow/runs/{uuid4()}/logs", headers=auth_headers)
    assert resp.status_code == 404


def test_run_logs_owner_succeeds(client, auth_headers):
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
        resp = client.get(f"/api/workflow/runs/{uuid4()}/logs", headers=auth_headers)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# WebSocket auth — token required, must match path user_id
# ---------------------------------------------------------------------------


def test_ws_rejects_missing_token(client):
    from starlette.websockets import WebSocketDisconnect
    import pytest

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/api/workflow/ws/workflows/{uuid4()}"):
            pass


def test_ws_rejects_mismatched_user(client, test_user):
    from starlette.websockets import WebSocketDisconnect
    from auth.utils import create_access_token
    import pytest

    token = create_access_token({"sub": str(test_user.id), "email": test_user.email})
    other_id = uuid4()  # path id different from token sub
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(
            f"/api/workflow/ws/workflows/{other_id}?token={token}"
        ):
            pass
