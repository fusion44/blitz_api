"""
Regression test: exec_bash_command must actually catch the timeout raised
by asyncio.wait_for.

`from redis.asyncio import ... TimeoutError` used to shadow the builtin, so
`except TimeoutError` never matched asyncio's builtin TimeoutError. Timed-out
commands fell through to the generic handler, the child process was never
terminated, and the caller got a misleading "unable to execute" error.
"""

from app.api.utils import exec_bash_command
from app.external.result_type.src.result.result import Err


async def test_exec_bash_command_reports_timeout():
    # `bash -c 'sleep 5'` with a 0.5s budget must time out
    res = await exec_bash_command("-c 'sleep 5'", timeout=0.5)

    assert isinstance(res, Err), "a timed-out command must return an Err"
    message = res.err_value.format_verbose().lower()
    assert "timed out" in message, (
        f"expected a timeout error, got: {message}"
    )
