import grpc
from fastapi import HTTPException, status
from loguru import logger

from app.lightning.exceptions import NodeNotFoundError


def generic_grpc_error_handler(error: grpc.aio._call.AioRpcError):
    details = error.details()
    logger.debug(details)

    raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=details)


# Substrings (matched case-insensitively) that indicate the backend failed to
# decode a payment request because the invoice is malformed or for the wrong
# network. Covers both LND (gRPC, e.g. the Go `strconv.ParseUint ... invalid
# syntax` a regtest invoice triggers on a mainnet node) and CLN (which prefixes
# its decode errors with `Invalid bolt11:`).
_PAY_REQ_DECODE_FAILURE_SIGNATURES = (
    "checksum failed",
    "invalid syntax",
    "invalid bech32",
    "bad bech32",
    "unable to decode",
    "invalid character",
    "invalid bolt11",
)

_PAY_REQ_DECODE_FAILURE_DETAIL = (
    "Could not decode the payment request. It may be malformed or intended "
    "for a different network (e.g. a regtest or testnet invoice on a mainnet "
    "node)."
)


def raise_for_pay_req_decode_error(details: str) -> None:
    """Raise HTTP 400 when `details` looks like an invoice-decode failure.

    Gives a single, clear message across LND and CLN instead of leaking the
    backend's raw error. Returns without raising for anything unrecognized so
    the caller can handle it (typically as a 500).
    """
    text = (details or "").lower()
    if any(sig in text for sig in _PAY_REQ_DECODE_FAILURE_SIGNATURES):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=_PAY_REQ_DECODE_FAILURE_DETAIL,
        )


async def alias_or_empty(func, node_pub: str) -> str:
    logger.debug(f"alias_or_empty({node_pub})")

    if not node_pub:
        logger.debug("alias_or_empty('') -> ''")

        return ""

    try:
        res = await func(node_pub)
        logger.debug(f"alias_or_empty -> {node_pub}")

        return res
    except NodeNotFoundError:
        logger.debug(f"NodeNotFoundError for node_pub={node_pub}")

        return ""
