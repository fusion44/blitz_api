"""
Regression tests: CLN helpers that shell out must not interpret
user-controlled input as shell syntax.

decode_pay_request forwarded a user-supplied bolt11 string straight into
`asyncio.create_subprocess_shell`, allowing arbitrary command execution
for any authenticated caller.
"""

import pytest


class _FakeProc:
    def __init__(self, stdout=b"{}", stderr=b""):
        self._stdout = stdout
        self._stderr = stderr

    async def communicate(self):
        return (self._stdout, self._stderr)


@pytest.fixture
def capture_exec(monkeypatch):
    """Capture argv passed to create_subprocess_exec and fail loudly if
    the shell variant is used at all."""
    from app.lightning.impl import cln_grpc

    calls = {"exec_argv": None, "shell_used": False}

    async def fake_exec(*argv, **kwargs):
        calls["exec_argv"] = list(argv)
        return _FakeProc()

    async def fake_shell(cmd, **kwargs):
        calls["shell_used"] = True
        return _FakeProc()

    monkeypatch.setattr(cln_grpc.asyncio, "create_subprocess_exec", fake_exec)
    monkeypatch.setattr(cln_grpc.asyncio, "create_subprocess_shell", fake_shell)
    monkeypatch.setattr(cln_grpc, "config", lambda key: "mainnet")
    return calls


async def test_make_local_call_passes_args_without_a_shell(capture_exec):
    from app.lightning.impl import cln_grpc

    payload = "lnbc1pdummy; touch /tmp/pwned"
    await cln_grpc._make_local_call("decodepay", f"bolt11={payload}")

    assert capture_exec["shell_used"] is False, (
        "must not run user input through a shell"
    )
    argv = capture_exec["exec_argv"]
    assert argv is not None, "create_subprocess_exec was not called"
    # the whole bolt11 value, metacharacters and all, must arrive as one
    # discrete argv token so the shell never sees it
    assert f"bolt11={payload}" in argv
    assert argv[0] == "lightning-cli"


async def test_blitz_cln_unlock_quotes_the_password(monkeypatch):
    """The CLN unlock password is interpolated into a shell command; it must
    be shell-quoted so metacharacters can't inject, and marked sensitive so
    it never lands in the logs."""
    import shlex

    from app.api.models import ProcessResult
    from app.external.result_type.src.result.result import Ok
    from app.lightning.impl.specializations import blitz_common

    captured = {}

    async def fake_exec(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        # return_code 2 == wrong password -> quick 401, skips the 60s poll
        return Ok(ProcessResult(2, "", ""))

    async def fake_redis_get(key):
        return "1"  # wallet locked

    monkeypatch.setattr(blitz_common, "exec_bash_command", fake_exec)
    monkeypatch.setattr(blitz_common, "redis_get", fake_redis_get)

    payload = "pw; touch /tmp/pwned"
    with pytest.raises(Exception):
        await blitz_common.blitz_cln_unlock("mainnet", payload)

    cmd = captured["command"]
    assert shlex.quote(payload) in cmd, "password must be shell-quoted"
    assert captured["kwargs"].get("sensitive") is True, (
        "password command must be marked sensitive"
    )
