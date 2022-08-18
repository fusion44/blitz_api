import json
from types import coroutine

import aiohttp
import requests
from decouple import config
from starlette import status

from app.models.bitcoind import BlockRpcFunc


class _BitcoinConfig:
    def __init__(self) -> None:
        self.network = config("network")
        self.zmq_block_rpc = BlockRpcFunc.from_string(config("bitcoind_zmq_block_rpc"))

        if self.network == "testnet":
            self.ip = config("bitcoind_ip_testnet")
            self.rpc_port = config("bitcoind_port_rpc_testnet")
            self.zmq_port = config("bitcoind_zmq_block_port_testnet")
        elif self.network == "regtest":
            self.ip = config("bitcoind_ip_regtest")
            self.rpc_port = config("bitcoind_port_rpc_regtest")
            self.zmq_port = config("bitcoind_zmq_block_port_regtest")
        else:
            self.ip = config("bitcoind_ip_mainnet")
            self.rpc_port = config("bitcoind_port_rpc_mainnet")
            self.zmq_port = config("bitcoind_zmq_block_port_mainnet")

        self.rpc_url = f"http://{self.ip}:{self.rpc_port}"
        self.zmq_url = f"tcp://{self.ip}:{self.zmq_port}"

        self.username = config("bitcoind_user")
        self.pw = config("bitcoind_pw")


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


async def bitcoin_rpc_async(method: str, params: list = []) -> coroutine:
    auth = aiohttp.BasicAuth(bitcoin_config.username, bitcoin_config.pw)
    headers = {"Content-type": "text/plain"}
    data = (
        '{"jsonrpc": "2.0", "method": "'
        + method
        + '", "id":"0", "params":'
        + json.dumps(params)
        + "}"
    )

    async with aiohttp.ClientSession(auth=auth, headers=headers) as session:
        async with session.post(bitcoin_config.rpc_url, data=data) as resp:
            if resp.status == status.HTTP_200_OK:
                return await resp.json()
            elif resp.status == status.HTTP_401_UNAUTHORIZED:
                return {
                    "error": "Access denied to Bitcoin Core RPC. Check if username and password is correct",
                    "status": status.HTTP_403_FORBIDDEN,
                }
            elif resp.status == status.HTTP_403_FORBIDDEN:
                return {
                    "error": "Access denied to Bitcoin Core RPC. If this is a remote node, check if 'network.rpcallowip=0.0.0.0/0' is set.",
                    "status": status.HTTP_403_FORBIDDEN,
                }
            else:
                return {
                    "error": f"Unknown answer from Bitcoin Core. Reason: {resp.reason}",
                    "status": resp.status,
                }
