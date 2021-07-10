import json
from types import coroutine
from typing import Dict, Final

import aiohttp
import requests
from decouple import config
from fastapi_plugins import redis_plugin


class BitcoinConfig:
    def __init__(self) -> None:
        self.network = config("network")

        if(self.network == "testnet"):
            self.ip = config("bitcoind_ip_testnet")
            self.rpc_port = config("bitcoind_port_testnet")
            self.zmq_port = config("bitcoind_port_zmq_testnet")
        else:
            self.ip = config("bitcoind_ip_mainnet")
            self.rpc_port = config("bitcoind_port_mainnet")
            self.zmq_port = config("bitcoind_port_zmq_mainnet")

        self.rpc_url = f"http://{self.ip}:{self.rpc_port}"
        self.zmq_url = f"tcp://{self.ip}:{self.zmq_port}"

        self.username = config("bitcoind_user")
        self.pw = config("bitcoind_pw")


bitcoin_config = BitcoinConfig()


class LightningConfig:
    def __init__(self) -> None:
        self.network = config("network")
        self.ln_node = config("ln_node")

        if(self.ln_node == "lnd"):
            # TODO: if macaroon and cert is not set in .env
            #       try to read it from the local drive
            self.lnd_macaroon = config("lnd_macaroon")
            self.lnd_cert = config("lnd_cert").encode('utf8')
            self.lnd_grpc_ip = config("lnd_grpc_ip")
            self.lnd_grpc_port = config("lnd_grpc_port")
            self.lnd_rest_port = config("lnd_rest_port")
            self.lnd_grpc_url = self.lnd_grpc_ip + ":" + self.lnd_grpc_port
        elif(self.ln_node == "clightning"):
            # TODO: implement c-lightning
            pass
        else:
            raise NameError(
                f"Node type \"{self.ln_node}\" is unknown. Use \"lnd\" or \"clightning\"")


lightning_config = LightningConfig()


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
    data = '{"jsonrpc": "2.0", "method": "' + \
        method + '", "id":"0", "params":' + json.dumps(params) + '}'
    return requests.post(bitcoin_config.rpc_url, auth=auth, headers=headers, data=data)


async def bitcoin_rpc_async(method: str, params: list = []) -> coroutine:
    auth = aiohttp.BasicAuth(bitcoin_config.username, bitcoin_config.pw)
    headers = {"Content-type": "text/plain"}
    data = '{"jsonrpc": "2.0", "method": "' + \
        method + '", "id":"0", "params":' + json.dumps(params) + '}'

    async with aiohttp.ClientSession(auth=auth, headers=headers) as session:
        async with session.post(bitcoin_config.rpc_url, data=data) as resp:
            return await resp.json()


async def send_sse_message(id: str, json_data: Dict):
    """Send a message to any SSE connections

    Parameters
    ----------
    id : str
        ID String von SSE class
    data : list, optional
        The data to include
    """

    await redis_plugin.redis.publish_json("default", {"id": id, "data": json_data})


class SSE():
    SYS_STATUS: Final = "sys_status"

    BTC_NETWORK_STATUS: Final = "btc_network_status"
    BTC_MEMPOOL_STATUS: Final = "btc_mempool_status"
    BTC_NEW_BLOC: Final = "btc_new_bloc"
    BTC_INFO: Final = "btc_info"
