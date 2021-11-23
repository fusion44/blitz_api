import json
import os
from types import coroutine
from typing import Dict

import aiohttp
import grpc
import requests
from decouple import config
from fastapi.encoders import jsonable_encoder
from fastapi_plugins import redis_plugin

import app.repositories.ln_impl.protos.lightning_pb2_grpc as lnrpc
import app.repositories.ln_impl.protos.router_pb2_grpc as routerrpc
import app.repositories.ln_impl.protos.walletunlocker_pb2_grpc as unlockerrpc


class BitcoinConfig:
    def __init__(self) -> None:
        self.network = config("network")

        if self.network == "testnet":
            self.ip = config("bitcoind_ip_testnet")
            self.rpc_port = config("bitcoind_port_rpc_testnet")
            self.zmq_port = config("bitcoind_port_zmq_hashblock_testnet")
        else:
            self.ip = config("bitcoind_ip_mainnet")
            self.rpc_port = config("bitcoind_port_rpc_mainnet")
            self.zmq_port = config("bitcoind_port_zmq_hashblock_mainnet")

        self.rpc_url = f"http://{self.ip}:{self.rpc_port}"
        self.zmq_url = f"tcp://{self.ip}:{self.zmq_port}"

        self.username = config("bitcoind_user")
        self.pw = config("bitcoind_pw")


bitcoin_config = BitcoinConfig()


class LightningConfig:
    def __init__(self) -> None:
        self.network = config("network")
        self.ln_node = config("ln_node")

        if self.ln_node == "lnd":
            # Due to updated ECDSA generated tls.cert we need to let gprc know that
            # we need to use that cipher suite otherwise there will be a handshake
            # error when we communicate with the lnd rpc server.
            os.environ["GRPC_SSL_CIPHER_SUITES"] = "HIGH+ECDSA"

            # Uncomment to see full gRPC logs
            # os.environ["GRPC_TRACE"] = 'all'
            # os.environ["GRPC_VERBOSITY"] = 'DEBUG'

            self.lnd_macaroon = config("lnd_macaroon")
            self._lnd_cert = bytes.fromhex(config("lnd_cert"))
            self._lnd_grpc_ip = config("lnd_grpc_ip")
            self._lnd_grpc_port = config("lnd_grpc_port")
            self._lnd_rest_port = config("lnd_rest_port")
            self._lnd_grpc_url = self._lnd_grpc_ip + ":" + self._lnd_grpc_port

            auth_creds = grpc.metadata_call_credentials(self.metadata_callback)
            ssl_creds = grpc.ssl_channel_credentials(self._lnd_cert)
            combined_creds = grpc.composite_channel_credentials(ssl_creds, auth_creds)

            self._channel = grpc.aio.secure_channel(self._lnd_grpc_url, combined_creds)
            self.lnd_stub = lnrpc.LightningStub(self._channel)
            self.router_stub = routerrpc.RouterStub(self._channel)
            self.wallet_unlocker = unlockerrpc.WalletUnlockerStub(self._channel)
        elif self.ln_node == "clightning":
            # TODO: implement c-lightning
            pass
        else:
            raise NameError(
                f'Node type "{self.ln_node}" is unknown. Use "lnd" or "clightning"'
            )

    def metadata_callback(self, context, callback):
        # for more info see grpc docs
        callback([("macaroon", self.lnd_macaroon)], None)


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

    await redis_plugin.redis.publish_json(
        "default", {"event": id, "data": json.dumps(jsonable_encoder(json_data))}
    )


class SSE:
    SYSTEM_INFO = "system_info"
    HARDWARE_INFO = "hardware_info"

    INSTALLED_APP_STATUS = "installed_app_status"

    BTC_NETWORK_STATUS = "btc_network_status"
    BTC_MEMPOOL_STATUS = "btc_mempool_status"
    BTC_NEW_BLOC = "btc_new_bloc"
    BTC_INFO = "btc_info"

    LN_INFO = "ln_info"
    LN_INFO_LITE = "ln_info_lite"
    LN_INVOICE_STATUS = "ln_invoice_status"
    LN_PAYMENT_STATUS = "ln_payment_status"
    LN_ONCHAIN_PAYMENT_STATUS = "ln_onchain_payment_status"

    WALLET_BALANCE = "wallet_balance"
