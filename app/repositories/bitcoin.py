import asyncio
import binascii
import json
import logging

import zmq
import zmq.asyncio
from fastapi import Request
from fastapi.exceptions import HTTPException
from starlette import status

from app.models.bitcoind import BlockchainInfo, BtcInfo, FeeEstimationMode, NetworkInfo
from app.utils import SSE, bitcoin_config, bitcoin_rpc_async, send_sse_message


async def get_blockchain_info() -> BlockchainInfo:
    result = await bitcoin_rpc_async("getblockchaininfo")
    if result["error"] != None:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail=result["error"]
        )
    return BlockchainInfo.from_rpc(result["result"])


async def estimate_fee(
    target_conf: int = 6,
    mode: FeeEstimationMode = FeeEstimationMode.CONSERVATIVE,
) -> int:
    result = await bitcoin_rpc_async("estimatesmartfee", [target_conf, mode])
    if result["error"] != None:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail=result["error"]
        )
    if "errors" in result["result"]:
        errors = "Bitcoin Core returned error(s):\n"
        for e in result["result"]["errors"]:
            errors += f"{e}\n"

        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail=errors[0 : len(errors) - 1]
        )

    # returned in BTC by Bitcoincoin Core => convert to msat
    rate_btc = result["result"]["feerate"]
    return rate_btc * 100000000


async def get_network_info() -> NetworkInfo:
    result = await bitcoin_rpc_async("getnetworkinfo")
    if result["error"] != None:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail=result["error"]
        )
    return NetworkInfo.from_rpc(result["result"])


async def get_btc_info() -> BtcInfo:
    binfo = await get_blockchain_info()
    ninfo = await get_network_info()
    return BtcInfo.from_rpc(binfo, ninfo)


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


async def handle_block_sub_redis(verbosity: int = 1) -> str:
    ctx = zmq.asyncio.Context()
    zmq_socket = ctx.socket(zmq.SUB)
    zmq_socket.setsockopt(zmq.RCVHWM, 0)
    zmq_socket.setsockopt_string(zmq.SUBSCRIBE, "hashblock")
    zmq_socket.connect(bitcoin_config.zmq_url)

    while True:
        _, body, _ = await zmq_socket.recv_multipart()
        hash = binascii.hexlify(body).decode("utf-8")
        r = await bitcoin_rpc_async("getblock", [hash, verbosity])
        await send_sse_message(SSE.BTC_NEW_BLOC, r["result"])


async def register_bitcoin_zmq_sub():
    loop = asyncio.get_event_loop()
    loop.create_task(handle_block_sub_redis())


async def _handle_gather_bitcoin_status():
    last_info = {}
    while True:
        try:
            info = await get_btc_info()
            info.verification_progress = round(info.verification_progress, 2)
        except HTTPException as e:
            logging.error(e.detail)
            await asyncio.sleep(2)
            continue

        if last_info != info:
            # only send data if anything has changed
            await send_sse_message(SSE.BTC_INFO, info.dict())
            last_info = info

        await asyncio.sleep(2)


async def register_bitcoin_status_gatherer():
    loop = asyncio.get_event_loop()
    loop.create_task(_handle_gather_bitcoin_status())
