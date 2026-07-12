import json

from app.api.error_report.response import build_error_response


def _body(resp):
    return json.loads(bytes(resp.body))


def test_string_detail_produces_error_message_object():
    resp = build_error_response(400, "bad thing")
    assert resp.status_code == 400
    body = _body(resp)
    assert body["detail"] == "bad thing"
    assert body["error_code"] == ""
    assert body["report"] is None
    assert body["trace"] is None


def test_sensitive_report_gated_off_by_default(monkeypatch):
    monkeypatch.setattr(
        "app.api.error_report.response.config",
        lambda name, default=False, cast=bool: False,
    )
    resp = build_error_response(500, "boom", report="/home/x/frame")
    assert _body(resp)["report"] is None


def test_report_included_when_flag_on(monkeypatch):
    monkeypatch.setattr(
        "app.api.error_report.response.config",
        lambda name, default=False, cast=bool: name == "BAPI_SEND_REPORT",
    )
    resp = build_error_response(500, "boom", report="details")
    assert _body(resp)["report"] == "details"


def test_non_sensitive_report_always_included(monkeypatch):
    monkeypatch.setattr(
        "app.api.error_report.response.config",
        lambda name, default=False, cast=bool: False,
    )
    resp = build_error_response(
        422, "bad", report=[{"msg": "x"}], report_sensitive=False
    )
    assert _body(resp)["report"] == [{"msg": "x"}]


def test_trace_gated(monkeypatch):
    monkeypatch.setattr(
        "app.api.error_report.response.config",
        lambda name, default=False, cast=bool: name == "BAPI_SEND_TRACE",
    )
    resp = build_error_response(500, "boom", trace=["l1", "l2"])
    assert _body(resp)["trace"] == ["l1", "l2"]
