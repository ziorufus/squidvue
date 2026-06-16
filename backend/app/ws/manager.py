from collections import defaultdict
from typing import Any

from fastapi import WebSocket


class WebSocketManager:
    def __init__(self) -> None:
        self.connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, channel: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections[channel].add(websocket)

    def disconnect(self, channel: str, websocket: WebSocket) -> None:
        if channel in self.connections:
            self.connections[channel].discard(websocket)
            if not self.connections[channel]:
                self.connections.pop(channel, None)

    async def broadcast(self, channel: str, payload: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for connection in list(self.connections.get(channel, [])):
            try:
                await connection.send_json(payload)
            except Exception:
                dead.append(connection)
        for connection in dead:
            self.disconnect(channel, connection)
