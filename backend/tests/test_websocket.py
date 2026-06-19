from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from auth.utils import create_access_token
from main import app


def test_websocket_rejects_without_token():
    """Unauthenticated connections must be closed, not served."""
    client = TestClient(app)
    user_id = str(uuid4())
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/api/workflow/ws/workflows/{user_id}"):
            pass


def test_websocket_accepts_matching_token():
    """A valid token whose sub matches the path connects and receives the feed."""
    client = TestClient(app)
    user_id = str(uuid4())
    token = create_access_token({"sub": user_id, "email": "ws@example.com"})

    with patch(
        "workflow.routes.workflow_router.DeploymentService.get_latest_runs_status",
        new=AsyncMock(return_value=[]),
    ):
        with client.websocket_connect(
            f"/api/workflow/ws/workflows/{user_id}?token={token}"
        ) as websocket:
            data = websocket.receive_json()
            assert data["type"] == "workflow_update"
            assert isinstance(data["data"], list)
