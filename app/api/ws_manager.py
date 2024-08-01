from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger


class WebSocketManager:
    def __init__(self):
        self._ctr = 0
        self.active_connections: dict[int, WebSocket] = {}

    async def connect(self, websocket: WebSocket) -> int:
        await websocket.accept()
        id = self._next_id()
        self.active_connections[id] = websocket
        logger.debug(f"Connecting Websocket with ID {id}")

        return id

    def disconnect(self, id: int):
        del self.active_connections[id]

    async def send_json(self, id: int, data: dict[str, Any]):
        websocket = self._get(id)
        await websocket.send_json(data=data)

    async def send_personal_message(self, message: str, id: int):
        await self._send(message, id)

    async def broadcast(self, message: str):
        for id in self.active_connections.keys():
            await self._send(message, id)

    async def broadcast_json(self, json_data: dict[str, Any]):
        for id in self.active_connections.keys():
            await self.send_json(id=id, data=json_data)

    async def _send(self, message: str, id: int):
        try:
            websocket = self._get(id)
            await websocket.send_text(message)
        except WebSocketDisconnect:
            self.disconnect(id)

    def _get(self, id: int):
        try:
            return self.active_connections[id]
        except Exception as e:
            raise e

    def _next_id(self):
        next_id = self._ctr
        self._ctr += 1
        return next_id
