import asyncio
import json

import pytest
from starlette.websockets import WebSocketDisconnect

from app.api.ws_manager import WebSocketManager


class FakeWebSocket:
    """Minimal stand-in for starlette WebSocket."""

    def __init__(self, incoming=None, raise_on_send=False, disconnect_on_receive=False):
        self.accepted = False
        self.closed_code = None
        self.sent = []
        self._incoming = list(incoming or [])
        self.raise_on_send = raise_on_send
        self.disconnect_on_receive = disconnect_on_receive

    async def accept(self):
        self.accepted = True

    async def receive_text(self):
        if self.disconnect_on_receive:
            raise WebSocketDisconnect(code=1000)
        if not self._incoming:
            await asyncio.sleep(3600)  # never sends -> block until cancelled
        return self._incoming.pop(0)

    async def send_text(self, text):
        if self.raise_on_send:
            raise RuntimeError("connection closed")
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


async def test_non_dict_json_first_frame_closes_4401(monkeypatch):
    monkeypatch.setattr(
        "app.api.ws_manager.JWTBearer",
        lambda: type("B", (), {"verify_jwt": lambda self, jwtoken: True})(),
    )
    mgr = WebSocketManager()
    ws = FakeWebSocket([json.dumps("42")])  # valid JSON, not a dict

    id_, authed = await mgr.connect(ws)

    assert authed is False
    assert id_ is None
    assert ws.closed_code == 4401


async def test_client_disconnect_during_auth_returns_unauthenticated(monkeypatch):
    mgr = WebSocketManager()
    ws = FakeWebSocket(disconnect_on_receive=True)

    id_, authed = await mgr.connect(ws)

    assert authed is False
    assert id_ is None
    # socket is already gone; connect() must not attempt to close() it
    assert ws.closed_code is None


async def test_broadcast_to_all_delivers_to_multiple_connections(monkeypatch):
    mgr = WebSocketManager()
    ws1 = FakeWebSocket()
    ws2 = FakeWebSocket()
    mgr._connections[1] = ws1
    mgr._connections[2] = ws2

    await mgr.broadcast_to_all("btc_info", {"blocks": 1})

    assert json.loads(ws1.sent[0]) == {"event": "btc_info", "data": {"blocks": 1}}
    assert json.loads(ws2.sent[0]) == {"event": "btc_info", "data": {"blocks": 1}}


async def test_send_to_single_drops_connection_on_send_failure(monkeypatch):
    mgr = WebSocketManager()
    ws = FakeWebSocket(raise_on_send=True)
    mgr._connections[1] = ws

    await mgr.send_to_single(1, "btc_info", {"blocks": 1})

    assert 1 not in mgr._connections


async def test_broadcast_to_all_drops_failing_connection_but_reaches_others(
    monkeypatch,
):
    mgr = WebSocketManager()
    bad_ws = FakeWebSocket(raise_on_send=True)
    good_ws = FakeWebSocket()
    mgr._connections[1] = bad_ws
    mgr._connections[2] = good_ws

    await mgr.broadcast_to_all("btc_info", {"blocks": 1})

    assert 1 not in mgr._connections
    assert 2 in mgr._connections
    assert json.loads(good_ws.sent[0]) == {"event": "btc_info", "data": {"blocks": 1}}
