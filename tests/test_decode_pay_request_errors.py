"""
Regression + unification tests for blitz_api#225.

Decoding a wrong-network invoice (e.g. a regtest `lnbcrt...` invoice on a
mainnet node) makes the backend fail with a cryptic error — LND leaks the Go
`strconv.ParseUint: parsing "rt500": invalid syntax`; CLN returns
`Invalid bolt11: ...`. All backends now funnel decode failures through
`raise_for_pay_req_decode_error`, returning one clear 400.
"""

import grpc
import pytest
from fastapi import HTTPException
from grpc.aio import AioRpcError, Metadata

from app.lightning.impl.cln_grpc import LnNodeCLNgRPC
from app.lightning.impl.cln_jrpc import LnNodeCLNjRPC
from app.lightning.impl.lnd_grpc import LnNodeLNDgRPC
from app.lightning.utils import raise_for_pay_req_decode_error


# --- the shared helper (the unification point) --------------------------------


@pytest.mark.parametrize(
    "details",
    [
        'strconv.ParseUint: parsing "rt500": invalid syntax',  # LND wrong network
        "checksum failed.",  # LND bad checksum
        "Invalid bolt11: Bad bech32 string",  # CLN bad bech32
        "Invalid bolt11: unknown chain: bcrt",  # CLN wrong network
    ],
)
def test_helper_maps_decode_failures_to_400(details):
    with pytest.raises(HTTPException) as exc:
        raise_for_pay_req_decode_error(details)
    assert exc.value.status_code == 400
    assert "network" in str(exc.value.detail).lower()


def test_helper_ignores_non_decode_errors():
    # a genuine backend error must pass through (caller turns it into a 500)
    raise_for_pay_req_decode_error(
        "rpc error: code = Unavailable desc = connection refused"
    )  # must not raise


# --- LND wiring ---------------------------------------------------------------


def _grpc_error(details: str) -> AioRpcError:
    return AioRpcError(
        grpc.StatusCode.UNKNOWN, Metadata(), Metadata(), details=details
    )


async def test_lnd_wrong_network_invoice_returns_400():
    node = LnNodeLNDgRPC()
    err = _grpc_error('strconv.ParseUint: parsing "rt500": invalid syntax')

    class FakeStub:
        async def DecodePayReq(self, req):
            raise err

    node._lnd_stub = FakeStub()

    with pytest.raises(HTTPException) as exc:
        await node.decode_pay_request("lnbcrt500u1pjvvyly...")

    assert exc.value.status_code == 400
    assert "strconv" not in str(exc.value.detail)


async def test_lnd_unexpected_error_still_500():
    node = LnNodeLNDgRPC()
    err = _grpc_error("rpc error: code = Unavailable desc = connection refused")

    class FakeStub:
        async def DecodePayReq(self, req):
            raise err

    node._lnd_stub = FakeStub()

    with pytest.raises(HTTPException) as exc:
        await node.decode_pay_request("lnbc1...")

    assert exc.value.status_code == 500


# --- CLN JSON-RPC wiring ------------------------------------------------------


async def test_cln_jrpc_wrong_network_returns_400():
    node = LnNodeCLNjRPC()

    async def fake_send(method, params=None):
        return {"error": {"message": "Invalid bolt11: unknown chain: bcrt"}}

    node._send_request = fake_send

    with pytest.raises(HTTPException) as exc:
        await node.decode_pay_request("lnbcrt500u1pjvvyly-jrpc")

    assert exc.value.status_code == 400


# --- CLN gRPC wiring ----------------------------------------------------------


async def test_cln_grpc_wrong_network_returns_400(monkeypatch):
    from app.lightning.impl import cln_grpc

    node = LnNodeCLNgRPC()

    async def fake_call(*args):
        # lightning-cli returns the decode error as JSON on stdout
        return (
            b'{"code": -32602, "message": "Invalid bolt11: unknown chain: bcrt"}',
            b"",
        )

    monkeypatch.setattr(cln_grpc, "_make_local_call", fake_call)

    with pytest.raises(HTTPException) as exc:
        await node.decode_pay_request("lnbcrt500u1pjvvyly-grpc")

    assert exc.value.status_code == 400


# --- CLN decodepay removal ----------------------------------------------------
# CLN deprecated `decodepay` in v24.11, disables it by default in v25.12
# (JSON-RPC -32601 'Command "decodepay" is deprecated') and removes it in
# v26.04. Calling it turned every Transactions load into a 500; both CLN
# backends must use `decode` instead.

_DECODE_RESULT = {
    "type": "bolt11 invoice",
    "valid": True,
    "currency": "bc",
    "created_at": 1759640918,
    "expiry": 3599,
    "payee": "027cd974e47086291bb8a5b0160a889c738f2712a703b8ea939985fd16f3aae67e",
    "amount_msat": 100000,
    "description": "test",
    "min_final_cltv_expiry": 80,
    "payment_secret": (
        "097795ffadc7849ab82737572eb3dd36c5dc5d17277effcdf2de709c07cd4a9a"
    ),
    "payment_hash": (
        "4620a5027133dd4f049df5e6c2024368e7ed804e9ad759feb349af2c2f60cde6"
    ),
}


async def test_cln_jrpc_uses_decode_not_decodepay():
    node = LnNodeCLNjRPC()
    seen = {}

    async def fake_send(method, params=None):
        seen["method"] = method
        return {"result": dict(_DECODE_RESULT)}

    node._send_request = fake_send

    req = await node.decode_pay_request("lnbc100u1p-jrpc-decode")

    assert seen["method"] == "decode"
    assert req.payment_hash == _DECODE_RESULT["payment_hash"]


async def test_cln_jrpc_decode_valid_false_returns_400():
    # unlike decodepay, decode reports recognized-but-invalid strings as a
    # normal result with valid=false + warning_* fields instead of an error
    node = LnNodeCLNjRPC()

    async def fake_send(method, params=None):
        return {
            "result": {
                "type": "bolt12 invoice",
                "valid": False,
                "warning_invoice_missing_amount": "invoice without an amount",
            }
        }

    node._send_request = fake_send

    with pytest.raises(HTTPException) as exc:
        await node.decode_pay_request("lni1-invalid")

    assert exc.value.status_code == 400
    assert "invoice without an amount" in str(exc.value.detail)


async def test_cln_grpc_uses_decode_not_decodepay(monkeypatch):
    import json

    from app.lightning.impl import cln_grpc

    node = LnNodeCLNgRPC()
    seen = {}

    async def fake_call(*args):
        seen["args"] = args
        return (json.dumps(_DECODE_RESULT).encode(), b"")

    monkeypatch.setattr(cln_grpc, "_make_local_call", fake_call)

    req = await node.decode_pay_request("lnbc100u1p-grpc-decode")

    assert seen["args"] == ("decode", "string=lnbc100u1p-grpc-decode")
    assert req.payment_hash == _DECODE_RESULT["payment_hash"]
