import asyncio
import json

from fastapi.encoders import jsonable_encoder
from loguru import logger

from app.auth.auth_bearer import JWTBearer

AUTH_TIMEOUT_SECONDS = 5


def _build_frame(event: str, data) -> str:
    return json.dumps({"event": event, "data": jsonable_encoder(data)})


class WebSocketManager:
    def __init__(self) -> None:
        self._connections: dict[int, object] = {}
        self._next_id = 0

    async def connect(self, websocket) -> tuple[int | None, bool]:
        await websocket.accept()
        try:
            raw = await asyncio.wait_for(
                websocket.receive_text(), timeout=AUTH_TIMEOUT_SECONDS
            )
        except (asyncio.TimeoutError, TimeoutError):
            await websocket.close(code=4408)
            return None, False

        try:
            msg = json.loads(raw)
            token = msg["token"] if msg.get("type") == "auth" else None
        except (ValueError, TypeError, KeyError):
            token = None

        if not token or not JWTBearer().verify_jwt(jwtoken=token):
            await websocket.close(code=4401)
            return None, False

        conn_id = self._next_id
        self._next_id += 1
        self._connections[conn_id] = websocket
        return conn_id, True

    def disconnect(self, id: int) -> None:
        self._connections.pop(id, None)

    async def send_to_single(self, id: int, event: str, data) -> None:
        ws = self._connections.get(id)
        if ws is None:
            return
        try:
            await ws.send_text(_build_frame(event, data))
        except Exception as e:
            logger.debug(f"dropping ws connection {id}: {e}")
            self.disconnect(id)

    async def broadcast_to_all(self, event: str, data) -> None:
        frame = _build_frame(event, data)
        for conn_id, ws in list(self._connections.items()):
            try:
                await ws.send_text(frame)
            except Exception as e:
                logger.debug(f"dropping ws connection {conn_id}: {e}")
                self.disconnect(conn_id)


ws_mgr = WebSocketManager()
