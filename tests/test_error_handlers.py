import json

from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient

import app.main as main
from app.api.models import ErrorMessage


def _body(resp):
    return json.loads(bytes(resp.body))


def test_framework_http_exception_uses_error_message_shape():
    # Framework-generated errors (404/405/...) are raised as the Starlette base
    # HTTPException, not fastapi's subclass. They must still get the full flat
    # ErrorMessage envelope, not FastAPI's default bare {"detail": "..."}.
    client = TestClient(main.app)  # no `with`: don't trigger lifespan/background tasks
    resp = client.get("/this-route-does-not-exist")
    assert resp.status_code == 404
    body = resp.json()
    assert isinstance(body["detail"], str)
    assert body["detail"] == "Not Found"
    assert body["error_code"] == ""
    assert body["report"] is None
    assert body["trace"] is None


async def test_string_detail_becomes_object():
    resp = await main.http_e_handler(None, HTTPException(400, detail="bad password"))
    assert resp.status_code == 400
    body = _body(resp)
    assert body["detail"] == "bad password"  # NOT a bare string body
    assert body["error_code"] == ""


async def test_errormessage_detail_gates_report_by_default():
    detail = ErrorMessage(
        detail="app failed",
        error_code="app_status_update_failed",
        report="/home/blitzapi/frame",
    ).model_dump()
    resp = await main.http_e_handler(None, HTTPException(500, detail=detail))
    body = _body(resp)
    assert body["detail"] == "app failed"
    assert body["error_code"] == "app_status_update_failed"
    assert body["report"] is None  # sensitive report gated off by default


async def test_validation_handler_keeps_field_array():
    exc = RequestValidationError(
        [
            {
                "type": "missing",
                "loc": ["body", "password"],
                "msg": "Field required",
                "input": None,
            }
        ]
    )
    resp = await main.valid_e_handler(None, exc)
    body = _body(resp)
    assert resp.status_code == 422
    assert body["detail"] == "Field required"
    assert body["error_code"] == "invalid_request_input"
    assert body["report"] is not None  # validation field array always kept


async def test_catchall_returns_error_message():
    resp = await main.unhandled_e_handler(None, ValueError("boom"))
    body = _body(resp)
    assert resp.status_code == 500
    assert body["error_code"] == "unknown"
    assert body["report"] is None  # gated off by default
