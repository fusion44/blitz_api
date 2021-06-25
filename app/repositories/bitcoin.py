import asyncio
import binascii
import json

import zmq
import zmq.asyncio
from app.utils import bitcoin_config, bitcoin_rpc_async
from fastapi import Request
from fastapi_plugins import redis_plugin


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
        await redis_plugin.redis.publish("default", json.dumps(r["result"]))


async def register_bitcoin_zmq_sub():
    loop = asyncio.get_event_loop()
    loop.create_task(handle_block_sub_redis())
