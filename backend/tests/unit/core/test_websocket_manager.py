from unittest.mock import AsyncMock

from core.websocket_manager import ConnectionManager


def _socket():
    sock = AsyncMock()
    sock.send_json = AsyncMock()
    return sock


async def test_broadcast_delivers_to_healthy_and_prunes_dead():
    manager = ConnectionManager()
    healthy = _socket()
    dead = _socket()
    dead.send_json.side_effect = RuntimeError("socket closed")

    manager.active_connections["u1"] = [healthy, dead]

    # Must not raise even though one socket fails.
    await manager.broadcast_to_user("u1", {"type": "ping"})

    healthy.send_json.assert_awaited_once_with({"type": "ping"})
    # Dead socket pruned; healthy one remains.
    assert manager.active_connections["u1"] == [healthy]


async def test_broadcast_all_dead_removes_user_key():
    manager = ConnectionManager()
    dead = _socket()
    dead.send_json.side_effect = RuntimeError("boom")
    manager.active_connections["u1"] = [dead]

    await manager.broadcast_to_user("u1", {"type": "ping"})

    assert "u1" not in manager.active_connections


async def test_broadcast_unknown_user_is_noop():
    manager = ConnectionManager()
    await manager.broadcast_to_user("nobody", {"type": "ping"})  # no raise


def test_disconnect_is_idempotent():
    manager = ConnectionManager()
    sock = _socket()
    manager.active_connections["u1"] = [sock]

    manager.disconnect("u1", sock)
    # Second call must not raise ValueError.
    manager.disconnect("u1", sock)

    assert "u1" not in manager.active_connections
