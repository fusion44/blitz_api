import asyncio
import json

import pytest

from app.api.ws_manager import WebSocketManager


class FakeWebSocket:
    """Minimal stand-in for starlette WebSocket."""

    def __init__(self, incoming=None):
        self.accepted = False
        self.closed_code = None
        self.sent = []
        self._incoming = list(incoming or [])

    async def accept(self):
        self.accepted = True

    async def receive_text(self):
        if not self._incoming:
            await asyncio.sleep(3600)  # never sends -> block until cancelled
        return self._incoming.pop(0)

    async def send_text(self, text):
        self.sent.append(text)

    async def close(self, code=1000):
        self.closed_code = code


async def test_valid_auth_registers_and_can_receive(monkeypatch):
    monkeypatch.setattr(
        "app.api.ws_manager.JWTBearer",
        lambda: type("B", (), {"verify_jwt": lambda self, jwtoken: True})(),
    )
    mgr = WebSocketManager()
    ws = FakeWebSocket([json.dumps({"type": "auth", "token": "good"})])

    id_, authed = await mgr.connect(ws)

    assert authed is True
    assert id_ is not None
    assert ws.accepted is True
    await mgr.send_to_single(id_, "btc_info", {"blocks": 1})
    assert json.loads(ws.sent[0]) == {"event": "btc_info", "data": {"blocks": 1}}


async def test_invalid_token_closes_4401(monkeypatch):
    monkeypatch.setattr(
        "app.api.ws_manager.JWTBearer",
        lambda: type("B", (), {"verify_jwt": lambda self, jwtoken: False})(),
    )
    mgr = WebSocketManager()
    ws = FakeWebSocket([json.dumps({"type": "auth", "token": "bad"})])

    id_, authed = await mgr.connect(ws)

    assert authed is False
    assert id_ is None
    assert ws.closed_code == 4401


async def test_auth_timeout_closes_4408(monkeypatch):
    monkeypatch.setattr("app.api.ws_manager.AUTH_TIMEOUT_SECONDS", 0.05)
    mgr = WebSocketManager()
    ws = FakeWebSocket([])  # never sends

    id_, authed = await mgr.connect(ws)

    assert authed is False
    assert ws.closed_code == 4408
