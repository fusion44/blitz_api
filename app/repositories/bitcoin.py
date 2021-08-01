import asyncio
import binascii
import json

import zmq
import zmq.asyncio
from app.utils import SSE, bitcoin_config, bitcoin_rpc_async, send_sse_message
from fastapi import Request
from fastapi.exceptions import HTTPException
from starlette import status


async def get_bitcoin_info():
    result = await bitcoin_rpc_async("getnetworkinfo")
    if(result["error"] != None):
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail=result["error"])
    r = result["result"]

    info = {}
    info["version"] = r["version"]
    info["subversion"] = r["subversion"]
    info["networkactive"] = r["networkactive"]
    info["networks"] = r["networks"]
    info["connections"] = r["connections"]
    info["connections_in"] = r["connections_in"]
    info["connections_out"] = r["connections_out"]

    result = await bitcoin_rpc_async("getblockchaininfo")
    if(result["error"] != None):
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail=result["error"])
    r = result["result"]

    info["chain"] = r["chain"]
    info["blocks"] = r["blocks"]
    info["headers"] = r["headers"]
    info["initialblockdownload"] = r["initialblockdownload"]
    info["size_on_disk"] = r["size_on_disk"]
    info["verification_progress"] = r["verificationprogress"]
    info["pruned"] = r["pruned"]

    return info


async def handle_block_sub(request: Request,  verbosity: int = 1) -> str:
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
        hash = binascii.hexlify(body).decode('utf-8')
        r = await bitcoin_rpc_async('getblock', [hash, verbosity])
        yield json.dumps(r["result"])


async def handle_block_sub_redis(verbosity: int = 1) -> str:
    ctx = zmq.asyncio.Context()
    zmq_socket = ctx.socket(zmq.SUB)
    zmq_socket.setsockopt(zmq.RCVHWM, 0)
    zmq_socket.setsockopt_string(zmq.SUBSCRIBE, "hashblock")
    zmq_socket.connect(bitcoin_config.zmq_url)

    while True:
        _, body, _ = await zmq_socket.recv_multipart()
        hash = binascii.hexlify(body).decode('utf-8')
        r = await bitcoin_rpc_async('getblock', [hash, verbosity])
        await send_sse_message(SSE.BTC_NEW_BLOC, r["result"])


async def register_bitcoin_zmq_sub():
    loop = asyncio.get_event_loop()
    loop.create_task(handle_block_sub_redis())


async def _handle_gather_bitcoin_info():
    last_info = {}
    while True:
        try:
            info = await get_bitcoin_info()
        except HTTPException as e:
            print(e)
            await asyncio.sleep(2)
            continue

        if last_info != info:
            # only send data if anything has changed
            await send_sse_message(SSE.BTC_INFO, info)
            last_info = info

        await asyncio.sleep(2)


async def register_bitcoin_info_gatherer():
    loop = asyncio.get_event_loop()
    loop.create_task(_handle_gather_bitcoin_info())
