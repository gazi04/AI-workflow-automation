from unittest.mock import MagicMock, patch
from uuid import uuid4

import httpx

from orchestration.tasks.slack_tasks import SLACK_RECONNECT_HINT, send_slack_message


def _response(payload: dict) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = payload
    return resp


def _run(post_return=None, post_side_effect=None, **kwargs):
    user_id = uuid4()
    with (
        patch(
            "orchestration.tasks.slack_tasks._fetch_bot_token",
            return_value="xoxb-test",
        ),
        patch(
            "orchestration.tasks.slack_tasks._mark_disconnected"
        ) as mark_disconnected,
        patch(
            "orchestration.tasks.slack_tasks.httpx.post",
            return_value=post_return,
            side_effect=post_side_effect,
        ) as post,
    ):
        try:
            result = send_slack_message.fn(
                user_id=user_id,
                channel=kwargs.get("channel", "#general"),
                message=kwargs.get("message", "hello"),
            )
        except Exception as exc:
            return None, post, mark_disconnected, user_id, exc
        return result, post, mark_disconnected, user_id, None


def test_ok_returns_channel_and_ts():
    result, post, _, _, exc = _run(
        _response({"ok": True, "channel": "C123", "ts": "1700000000.000100"})
    )

    assert exc is None
    assert result == {
        "status": "sent",
        "channel": "C123",
        "ts": "1700000000.000100",
    }
    _, kwargs = post.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer xoxb-test"
    assert kwargs["json"] == {"channel": "#general", "text": "hello"}
    assert kwargs["timeout"] == 10


def test_channel_not_found_raises_value_error():
    _, _, mark_disconnected, _, exc = _run(
        _response({"ok": False, "error": "channel_not_found"})
    )

    assert isinstance(exc, ValueError)
    assert "channel_not_found" in str(exc)
    mark_disconnected.assert_not_called()


def test_revoked_token_marks_account_disconnected_and_raises_permission_error():
    _, _, mark_disconnected, user_id, exc = _run(
        _response({"ok": False, "error": "token_revoked"})
    )

    assert isinstance(exc, PermissionError)
    assert str(exc) == SLACK_RECONNECT_HINT
    mark_disconnected.assert_called_once_with(user_id)


def test_unknown_slack_error_raises_runtime_error():
    _, _, _, _, exc = _run(_response({"ok": False, "error": "ratelimited"}))

    assert isinstance(exc, RuntimeError)
    assert "ratelimited" in str(exc)


def test_network_error_propagates_for_prefect_retry():
    _, _, mark_disconnected, _, exc = _run(
        post_side_effect=httpx.ConnectTimeout("slow")
    )

    assert isinstance(exc, httpx.HTTPError)
    mark_disconnected.assert_not_called()
