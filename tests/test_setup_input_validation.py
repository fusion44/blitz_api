"""
Regression tests for the RaspiBlitz setup input validation and file handling.

Values from POST /setup/setup-start-done are written to the setup file, which
provisioning sources as bash as root, so the charset validators are the
boundary between an unauthenticated request body and root command execution.
"""

import os
import stat

from app.system.impl.raspiblitz_utils import name_valid, password_valid

# Values that must never reach a sourced-as-bash file. No spaces: the validators
# reject those separately, and an attacker does not need them ($IFS, redirects).
SHELL_METACHAR_INPUTS = [
    "abcdefgh';touch/tmp/pwned;'",
    "abcdefgh$(touch/tmp/pwned)",
    "abcdefgh`touch/tmp/pwned`",
    "abcdefgh;touch/tmp/pwned",
    "abcdefgh|touch/tmp/pwned",
    "abcdefgh&touch/tmp/pwned",
    "abcdefgh>/tmp/pwned",
    "abcdefgh\ntouch/tmp/pwned",
]


def test_validators_return_real_booleans():
    """The setup router checks `is False`, so returning None was a bypass."""
    assert password_valid("bad'chars") is False
    assert name_valid("bad'chars") is False
    assert password_valid("goodpassword123") is True
    assert name_valid("goodhostname") is True


def test_password_valid_rejects_shell_metacharacters():
    for candidate in SHELL_METACHAR_INPUTS:
        assert password_valid(candidate) is False, f"accepted: {candidate!r}"


def test_name_valid_rejects_shell_metacharacters():
    for candidate in SHELL_METACHAR_INPUTS:
        assert name_valid(candidate) is False, f"accepted: {candidate!r}"


def test_validators_reject_trailing_newline():
    """re.match's `$` also matches before a final newline; fullmatch does not."""
    assert password_valid("abcd1234\n") is False
    assert name_valid("hostname\n") is False


def test_validators_still_accept_legitimate_values():
    assert password_valid("Sat0shi-Nakamoto_2009.") is True
    assert name_valid("my-blitz_01.node") is True
    # length and space rules must keep working
    assert password_valid("short7") is False
    assert password_valid("has space here") is False
    assert name_valid("ab") is False


async def _call_start_done(monkeypatch, redis_values, **overrides):
    """Invoke setup_start_done with a faked key-value store."""
    import pytest
    from fastapi import HTTPException

    from app.setup.impl.raspiblitz import router as setup_router

    async def fake_redis_get(key):
        return redis_values.get(key, "")

    monkeypatch.setattr(setup_router, "redis_get", fake_redis_get)

    payload = {
        "hostname": "myblitz",
        "forceFreshSetup": False,
        "keepBlockchain": False,
        "lightning": "none",
        "passwordA": "goodpassword1",
        "passwordB": "goodpassword1",
        "passwordC": "",
    }
    payload.update(overrides)
    data = setup_router.StartDoneData(**payload)

    with pytest.raises(HTTPException) as excinfo:
        await setup_router.setup_start_done(data)
    return excinfo.value


async def test_finalized_node_rejects_setup_start_done(monkeypatch):
    """`state` is attacker-writable; `setupPhase` stays "done" after setup."""
    exc = await _call_start_done(
        monkeypatch, {"state": "waitsetup", "setupPhase": "done"}
    )
    assert exc.status_code == 405


async def test_setup_start_done_rejects_shell_metacharacter_hostname(monkeypatch):
    """hostname is interpolated unquoted into the sourced-as-root file."""
    exc = await _call_start_done(
        monkeypatch,
        {"state": "waitsetup", "setupPhase": "setup"},
        hostname="blitz;touch/tmp/pwned",
    )
    assert exc.status_code == 400


async def test_setup_start_done_rejects_shell_metacharacter_password(monkeypatch):
    exc = await _call_start_done(
        monkeypatch,
        {"state": "waitsetup", "setupPhase": "setup"},
        passwordA="abcdefgh';touch/tmp/pwned;'",
    )
    assert exc.status_code == 400


async def _reject_before_shell(monkeypatch, call):
    """Run `call` and return the shell commands it attempted."""
    from app.system.impl import raspiblitz as rb

    monkeypatch.setattr(
        rb.RaspiBlitzSystem, "_check_shell_scripts_status", lambda self: None
    )
    commands = []

    async def fake_exec(command, **kwargs):
        commands.append(command)
        raise AssertionError(f"reached the shell with: {command!r}")

    monkeypatch.setattr(rb, "exec_bash_command", fake_exec)
    await call(rb.RaspiBlitzSystem())
    return commands


async def test_login_rejects_metacharacters_before_shell(monkeypatch):
    """Login interpolates the password into a shell string; gate it first."""
    from fastapi import HTTPException

    from app.system.models import LoginInput

    for candidate in SHELL_METACHAR_INPUTS:

        async def call(system, candidate=candidate):
            try:
                await system.login(LoginInput(password=candidate))
            except HTTPException as e:
                assert e.status_code == 401, f"unexpected status for {candidate!r}"

        assert await _reject_before_shell(monkeypatch, call) == []


async def test_change_password_rejects_metacharacters_before_shell(monkeypatch):
    from fastapi import HTTPException

    for candidate in SHELL_METACHAR_INPUTS:

        async def call(system, candidate=candidate):
            try:
                await system.change_password("a", candidate, "goodpassword1")
            except HTTPException as e:
                assert e.status_code == 400, f"unexpected status for {candidate!r}"

        assert await _reject_before_shell(monkeypatch, call) == []


async def test_change_password_rejects_metacharacter_type(monkeypatch):
    """`type` is interpolated unquoted, so the a|b|c gate is load-bearing."""
    from fastapi import HTTPException

    async def call(system):
        try:
            await system.change_password(
                "a;touch/tmp/pwned", "goodpassword1", "goodpassword2"
            )
        except HTTPException as e:
            assert e.status_code == 400

    assert await _reject_before_shell(monkeypatch, call) == []


def test_setup_file_is_created_private(tmp_path):
    """Holds cleartext passwords and seed words on a mode=0777 tmpfs."""
    from app.setup.impl.raspiblitz.router import write_text_file

    target = tmp_path / "raspiblitz.setup"
    write_text_file(str(target), ["passwordA='secret123'", ""])

    mode = stat.S_IMODE(os.stat(target).st_mode)
    assert mode == 0o600, f"expected 0600, got {oct(mode)}"

    # rewriting an existing file must not silently widen it either
    os.chmod(target, 0o644)
    write_text_file(str(target), ["passwordA='secret123'", ""])
    mode = stat.S_IMODE(os.stat(target).st_mode)
    assert mode == 0o600, f"rewrite left mode {oct(mode)}"
