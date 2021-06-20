import binascii
import json
from hashlib import sha256

import zmq
import zmq.asyncio
from app.utils import bitcoin_config, bitcoin_rpc_async
from fastapi import Request


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
