import json

from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.auth.auth_handler import sign_jwt
from app.main import app

client = TestClient(app)


def test_ws_valid_auth_receives_startup_frame():
    # conftest.py sets BAPI_JWT_SECRET/ALGORITHM, so sign_jwt() is a valid token
    token = sign_jwt()
    with client.websocket_connect("/ws") as ws:
        ws.send_text(json.dumps({"type": "auth", "token": token}))
        frame = json.loads(ws.receive_text())
        assert frame["event"] == "system_startup_info"
        assert "data" in frame


def test_ws_bad_token_is_closed_4401():
    with client.websocket_connect("/ws") as ws:
        ws.send_text(json.dumps({"type": "auth", "token": "not-a-jwt"}))
        try:
            ws.receive_text()
            assert False, "expected the server to close the connection"
        except WebSocketDisconnect as e:
            assert e.code == 4401
