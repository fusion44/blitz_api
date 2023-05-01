import grpc
from fastapi import HTTPException
from loguru import logger

from app.lightning.exceptions import NodeNotFoundError


def generic_grpc_error_handler(error: grpc.aio._call.AioRpcError):
    details = error.details()
    logger.debug(details)

    raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=details)


async def alias_or_empty(func, node_pub: str) -> str:
    logger.debug(f"alias_or_empty({node_pub})")

    if not node_pub:
        logger.debug(f"alias_or_empty('') -> ''")

        return ""

    try:
        res = await func(node_pub)
        logger.debug(f"alias_or_empty -> {node_pub}")

        return res
    except NodeNotFoundError:
        logger.debug(f"NodeNotFoundError for node_pub={node_pub}")

        return ""
