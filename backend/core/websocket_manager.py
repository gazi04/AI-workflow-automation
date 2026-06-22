from typing import List, Dict
from fastapi import WebSocket

from core.setup_logging import setup_logger

logger = setup_logger("WebSocket Manager")


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)

    def disconnect(self, user_id: str, websocket: WebSocket):
        connections = self.active_connections.get(user_id)
        if not connections:
            return
        # Guard the remove so a double disconnect (e.g. router finally + dead-socket
        # pruning) can't raise ValueError.
        if websocket in connections:
            connections.remove(websocket)
        if not connections:
            del self.active_connections[user_id]

    async def send_personal_message(self, message: any, websocket: WebSocket):
        await websocket.send_json(message)

    async def broadcast_to_user(self, user_id: str, message: any):
        connections = self.active_connections.get(user_id)
        if not connections:
            return
        # One dead socket must not abort delivery to the user's other tabs.
        # Send to each independently, then prune the ones that failed.
        dead: List[WebSocket] = []
        for connection in list(connections):
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Dropping dead socket for user {user_id}: {e}")
                dead.append(connection)
        for connection in dead:
            self.disconnect(user_id, connection)


manager = ConnectionManager()
