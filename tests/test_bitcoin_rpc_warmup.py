"""
Regression test for blitz_api#287.

Bitcoin Core returns the -28 "Loading block index" warmup error as an
HTTP 200 with a JSON-RPC error body. _process_response returned that body
unchanged, so it had an "error" key but no "status" key, and callers doing
`raise HTTPException(result["status"], ...)` crashed with KeyError: 'status'
instead of the HTTPException(425) the startup warmup loop expects.
"""

import pytest
from starlette import status

from app.bitcoind.utils import _process_response


class _FakeResp:
    def __init__(self, http_status, body, reason="OK"):
        self.status = http_status
        self._body = body
        self.reason = reason

    async def json(self):
        return self._body


@pytest.mark.parametrize(
    "message",
    [
        "Loading block index…",  # blitz_api#287
        "Verifying blocks…",  # blitz_api#285
        "Starting network threads…",
    ],
)
async def test_200_warmup_error_is_normalized_to_too_early(message):
    resp = _FakeResp(
        status.HTTP_200_OK,
        {
            "jsonrpc": "2.0",
            "error": {"code": -28, "message": message},
            "id": 6,
        },
    )

    out = await _process_response(resp)

    assert out["status"] == status.HTTP_425_TOO_EARLY
    assert out["error"]  # a human-readable message, not the raw dict


async def test_200_success_body_is_passed_through():
    body = {"jsonrpc": "2.0", "result": {"blocks": 42}, "error": None, "id": 1}
    resp = _FakeResp(status.HTTP_200_OK, body)

    out = await _process_response(resp)

    assert out == body
