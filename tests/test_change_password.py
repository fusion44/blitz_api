"""
Regression tests for the change-password endpoint.

- Passwords were accepted as query parameters, so they leaked into access
  logs, proxy logs and browser history. They must travel in the request body.
- The RaspiBlitz password scripts were called without sensitive=True, so the
  plaintext passwords were written to the debug log.
"""

from app.api.models import ProcessResult
from app.external.result_type.src.result.result import Ok


def test_change_password_uses_request_body_not_query():
    from app.main import app

    spec = app.openapi()
    path = next(p for p in spec["paths"] if p.endswith("change-password"))
    operation = spec["paths"][path]["post"]

    param_names = {p["name"] for p in operation.get("parameters", [])}
    assert "old_password" not in param_names, "password must not be a query param"
    assert "new_password" not in param_names, "password must not be a query param"
    assert "requestBody" in operation, "passwords must be sent in the request body"


async def test_raspiblitz_change_password_calls_are_sensitive(monkeypatch):
    from app.system.impl import raspiblitz as rb

    # the shell-script existence check would exit(1) in the test env
    monkeypatch.setattr(
        rb.RaspiBlitzSystem, "_check_shell_scripts_status", lambda self: None
    )
    system = rb.RaspiBlitzSystem()
    calls = []

    async def fake_exec(command, **kwargs):
        calls.append(kwargs)
        # 'check' -> correct=1; 'set' -> no error key
        return Ok(ProcessResult(0, "correct=1\n", ""))

    monkeypatch.setattr(rb, "exec_bash_command", fake_exec)
    monkeypatch.setattr(rb, "password_valid", lambda p: True)

    await system.change_password("a", "oldpass12", "newpass12")

    assert len(calls) == 2, "expected a check call and a set call"
    assert all(c.get("sensitive") is True for c in calls), (
        "password script calls must be marked sensitive so they aren't logged"
    )
