import asyncio
import binascii
import json

import zmq
import zmq.asyncio
from aiohttp import client_exceptions
from fastapi import Request
from fastapi.exceptions import HTTPException
from loguru import logger
from starlette import status

from app.api.utils import SSE, broadcast_sse_msg
from app.bitcoind.models import (
    BlockchainInfo,
    BlockRpcFunc,
    BtcInfo,
    FeeEstimationMode,
    NetworkInfo,
    RawTransaction,
)
from app.bitcoind.utils import bitcoin_config, bitcoin_rpc_async

_initialized = False


@logger.catch(exclude=(HTTPException,))
async def initialize_bitcoin_repo() -> bool:
    global _initialized
    if _initialized:
        return True

    logger.info("Initializing bitcoin repository")
    # Wait until the bitcoin node is ready to accept RPC calls
    while not _initialized:
        try:
            await get_blockchain_info()
            _initialized = True
            logger.success("Bitcoin repository initialized")
            return True
        except client_exceptions.ClientConnectorError:
            logger.debug("Unable to connect to Bitcoin Core, waiting 5 seconds...")
            await asyncio.sleep(5)
        except HTTPException as e:
            if e.status_code == status.HTTP_425_TOO_EARLY:
                logger.info("Bitcoin Core initializing, waiting 10 seconds...")
                await asyncio.sleep(10)
                continue

            if e.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR:
                logger.error(e.detail)

            logger.debug(
                f"Connected to Bitcoin Core but it seems to be initializing, waiting 2 seconds... \n{e.detail}"
            )

            await asyncio.sleep(2)


@logger.catch(exclude=(HTTPException,))
async def get_blockchain_info() -> BlockchainInfo:
    result = await bitcoin_rpc_async("getblockchaininfo")

    if result["error"] != None:
        raise HTTPException(result["status"], detail=result["error"])

    return BlockchainInfo.from_rpc(result["result"])


@logger.catch(exclude=(HTTPException,))
async def estimate_fee(
    target_conf: int = 6,
    mode: FeeEstimationMode = FeeEstimationMode.CONSERVATIVE,
) -> int:
    result = await bitcoin_rpc_async("estimatesmartfee", [target_conf, mode])

    if result["error"] != None:
        raise HTTPException(result["status"], detail=result["error"])

    if "errors" in result["result"]:
        errors = "Bitcoin Core returned error(s):\n"
        for e in result["result"]["errors"]:
            errors += f"{e}\n"

        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail=errors[0 : len(errors) - 1]
        )

    # returned in BTC by Bitcoin Core => convert to msat
    rate_btc = result["result"]["feerate"]

    return rate_btc * 100000000


@logger.catch(exclude=(HTTPException,))
async def get_network_info() -> NetworkInfo:
    result = await bitcoin_rpc_async("getnetworkinfo")

    if result["error"] != None:
        raise HTTPException(result["status"], detail=result["error"])

    return NetworkInfo.from_rpc(result["result"])


@logger.catch(exclude=(HTTPException,))
async def get_raw_transaction(txid: str) -> RawTransaction:
    result = await bitcoin_rpc_async("getrawtransaction", [txid, 1])

    if result["error"] == None:
        return RawTransaction.from_rpc(result["result"])

    if "No such mempool or blockchain transaction." in result["error"]:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=result["error"])

    if "must be of length 64" in result["error"]:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=result["error"])

    raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=result["error"])


@logger.catch(exclude=(HTTPException,))
async def get_btc_info() -> BtcInfo:
    binfo = await get_blockchain_info()
    ninfo = await get_network_info()

    return BtcInfo.from_rpc(binfo, ninfo)


@logger.catch(exclude=(HTTPException,))
async def handle_block_sub(request: Request, verbosity: int = 1) -> str:
    ctx = zmq.asyncio.Context()
    zmq_socket = ctx.socket(zmq.SUB)
    zmq_socket.setsockopt(zmq.RCVHWM, 0)
    zmq_socket.setsockopt_string(zmq.SUBSCRIBE, "hashblock")
    zmq_socket.connect(bitcoin_config.zmq_url)

    while True:
        if await request.is_disconnected():
            ctx.destroy()
            break

        _, body, _ = await zmq_socket.recv_multipart()
        hash = binascii.hexlify(body).decode("utf-8")
        r = await bitcoin_rpc_async("getblock", [hash, verbosity])

        yield json.dumps(r["result"])


@logger.catch(exclude=(HTTPException,))
async def handle_block_sub_redis(verbosity: int = 1) -> str:
    ctx = zmq.asyncio.Context()
    zmq_socket = ctx.socket(zmq.SUB)
    zmq_socket.setsockopt(zmq.RCVHWM, 0)
    zmq_socket.setsockopt_string(zmq.SUBSCRIBE, bitcoin_config.zmq_block_rpc)
    zmq_socket.connect(bitcoin_config.zmq_url)

    while True:
        hash = ""
        _, body, _ = await zmq_socket.recv_multipart()
        if bitcoin_config.zmq_block_rpc == BlockRpcFunc.HASHBLOCK:
            hash = binascii.hexlify(body).decode("utf-8")
        elif bitcoin_config.zmq_block_rpc == BlockRpcFunc.RAWBLOCK:
            r1 = await bitcoin_rpc_async("getbestblockhash", [])
            hash = r1["result"]
        else:
            raise NotImplementedError(
                f"ZMQ block function {bitcoin_config.zmq_block_rpc} not supported"
            )

        r = await bitcoin_rpc_async("getblock", [hash, verbosity])
        await broadcast_sse_msg(SSE.BTC_NEW_BLOC, r["result"])


@logger.catch(exclude=(HTTPException,))
async def register_bitcoin_zmq_sub():
    loop = asyncio.get_event_loop()
    loop.create_task(handle_block_sub_redis())


@logger.catch(exclude=(HTTPException,))
async def _handle_gather_bitcoin_status():
    last_info = {}
    while True:
        try:
            info = await get_btc_info()
            if info == None:
                continue

            info.verification_progress = round(info.verification_progress, 2)
        except HTTPException as e:
            logger.error(e.detail)
            await asyncio.sleep(2)
            continue

        if last_info != info:
            # only send data if anything has changed
            await broadcast_sse_msg(SSE.BTC_INFO, info.dict())
            last_info = info

        await asyncio.sleep(2)


@logger.catch(exclude=(HTTPException,))
async def register_bitcoin_status_gatherer():
    loop = asyncio.get_event_loop()
    loop.create_task(_handle_gather_bitcoin_status())
