import itertools
import json
from types import coroutine

import aiohttp
import requests
from loguru import logger
from starlette import status

from app.api.config import config
from app.bitcoind.models import BlockRpcFunc


class _BitcoinConfig:
    def __init__(self) -> None:
        self.network = config("BAPI_NETWORK")
        self.zmq_block_rpc = BlockRpcFunc.from_string(
            str(config("BAPI_BITCOIND_ZMQ_BLOCK_RPC", default="hashblock"))
        )

        self.ip = config("BAPI_BITCOIND_ADDRESS")
        self.rpc_port = config("BAPI_BITCOIND_PORT_RPC")
        self.zmq_port = config("BAPI_BITCOIND_ZMQ_BLOCK_PORT")

        self.rpc_url = f"http://{self.ip}:{self.rpc_port}"
        self.zmq_url = f"tcp://{self.ip}:{self.zmq_port}"

        self.username = config("BAPI_BITCOIND_USER")
        self.pw = config("BAPI_BITCOIND_RPC_PW")

        logger.trace(f"Built Bitcoin config: {self.rpc_url} {self.zmq_url}")


bitcoin_config = _BitcoinConfig()


def bitcoin_rpc(method: str, params: list = []) -> requests.Response:
    """Make an RPC request to the Bitcoin daemon

    Connection parameters are read from the .env file.

    Parameters
    ----------
    method : str
        The method to call.
    params : list, optional
        Any parameters to include with the call
    """
    auth = (bitcoin_config.username, bitcoin_config.pw)
    headers = {"Content-type": "text/plain"}
    data = (
        '{"jsonrpc": "2.0", "method": "'
        + method
        + '", "id":"0", "params":'
        + json.dumps(params)
        + "}"
    )
    return requests.post(bitcoin_config.rpc_url, auth=auth, headers=headers, data=data)


# https://github.com/python/cpython/blob/3.10/Lib/asyncio/tasks.py#L31
_generate_rpc_id = itertools.count(1).__next__


async def bitcoin_rpc_async(method: str, params: list = []) -> coroutine:
    auth = aiohttp.BasicAuth(bitcoin_config.username, bitcoin_config.pw)
    headers = {"Content-type": "text/json"}
    data = (
        '{"jsonrpc": "2.0", "method": "'
        + method
        + f'", "id":{_generate_rpc_id()}, "params":'
        + json.dumps(params)
        + "}"
    )
    try:
        async with aiohttp.ClientSession(auth=auth, headers=headers) as session:
            async with session.post(bitcoin_config.rpc_url, data=data) as resp:
                return await _process_response(resp)

    except aiohttp.client_exceptions.ClientConnectionError as e:
        return {
            "error": f"Aiohttp client connection error: {str(e)}",
            "status": status.HTTP_503_SERVICE_UNAVAILABLE,
        }

    except aiohttp.client_exceptions.ClientError as e:
        return {
            "error": f"Aiohttp client error: {str(e)}",
            "status": status.HTTP_503_SERVICE_UNAVAILABLE,
        }


async def _process_response(resp: aiohttp.ClientResponse):
    if resp.status == status.HTTP_200_OK:
        return await resp.json()

    if resp.status == status.HTTP_401_UNAUTHORIZED:
        return {
            "error": (
                "Access denied to Bitcoin Core RPC. Check if "
                "username and password is correct"
            ),
            "status": status.HTTP_403_FORBIDDEN,
        }

    if resp.status == status.HTTP_403_FORBIDDEN:
        return {
            "error": (
                "Access denied to Bitcoin Core RPC. If this is a remote node, "
                "check if 'network.rpcallowip=0.0.0.0/0' is set."
            ),
            "status": status.HTTP_403_FORBIDDEN,
        }

    e = await resp.json()
    m = e["error"]["message"]

    if e["error"]:
        if (
            "Loading block index" in m
            or "Verifying blocks" in m
            or "Starting network threads" in m
        ):
            return {
                "error": (
                    "Initializing Bitcoin Core (loading, verifying "
                    "blocks or starting network threads etc)"
                ),
                "status": status.HTTP_425_TOO_EARLY,
            }
        if "No such mempool or blockchain transaction." in m:
            return {
                "error": "No such mempool or blockchain transaction.",
                "status": status.HTTP_404_NOT_FOUND,
            }
        if "parameter 1 must be of length 64" in m:
            return {
                "error": m,
                "status": status.HTTP_400_BAD_REQUEST,
            }
        if "Use -txindex" in m:
            return {
                "error": "-txindex option for Bitcoin Core not enabled",
                "status": status.HTTP_400_BAD_REQUEST,
            }

    return {
        "error": f"Unknown answer from Bitcoin Core. Reason: {resp.reason}",
        "status": resp.status,
    }
