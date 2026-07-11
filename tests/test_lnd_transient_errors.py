"""
Regression test for blitz_api#247 (original symptom).

While the LND RPC server is still starting up it answers gRPC calls with
"the RPC server is in the process of starting up, but not yet ready to accept
calls". The API mapped only the "wallet locked" case to a proper status and
returned a bare 500 for everything else, so list-all-tx (and friends) 500'd
during LND startup. The startup case should map to a transient status the
client can retry.
"""

import pytest
from fastapi import HTTPException
from starlette import status

from app.lightning.impl import lnd_grpc


class _FakeGrpcError:
    def __init__(self, details):
        self._details = details

    def details(self):
        return self._details


def test_wallet_locked_maps_to_423():
    err = _FakeGrpcError("wallet locked, unlock it to enable full RPC access")
    with pytest.raises(HTTPException) as exc:
        lnd_grpc._check_transient_ln_error(err)
    assert exc.value.status_code == status.HTTP_423_LOCKED


def test_rpc_starting_up_maps_to_425():
    err = _FakeGrpcError(
        "the RPC server is in the process of starting up, but not yet "
        "ready to accept calls"
    )
    with pytest.raises(HTTPException) as exc:
        lnd_grpc._check_transient_ln_error(err)
    assert exc.value.status_code == status.HTTP_425_TOO_EARLY


def test_unrelated_error_does_not_raise():
    # unknown errors are left for the caller to turn into a 500
    lnd_grpc._check_transient_ln_error(_FakeGrpcError("some unrelated error"))


def test_none_details_does_not_raise():
    lnd_grpc._check_transient_ln_error(_FakeGrpcError(None))
