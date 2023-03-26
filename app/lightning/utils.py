import grpc


def generic_grpc_error_handler(error: grpc.aio._call.AioRpcError):
    details = error.details()
    logger.debug(details)

    raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=details)
