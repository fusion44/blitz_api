import array
import json
import logging
import os
import random
import time
from types import coroutine
from typing import Dict

import aiohttp
import grpc
import requests
from decouple import config
from fastapi.encoders import jsonable_encoder
from fastapi_plugins import redis_plugin
from starlette import status

node_type = config("ln_node")
if node_type == "lnd":
    import app.repositories.ln_impl.protos.lnd.lightning_pb2_grpc as lnrpc
    import app.repositories.ln_impl.protos.lnd.router_pb2_grpc as routerrpc
    import app.repositories.ln_impl.protos.lnd.walletunlocker_pb2_grpc as unlockerrpc
elif node_type == "cln_grpc":
    import app.repositories.ln_impl.protos.cln.node_pb2_grpc as clnrpc
elif node_type == "cln_unix_socket":
    from pyln.client import LightningRpc
else:
    raise ValueError(f"Unknown node type: {node_type}")


from app.models.bitcoind import BlockRpcFunc


class BitcoinConfig:
    def __init__(self) -> None:
        self.network = config("network")
        self.zmq_block_rpc = BlockRpcFunc.from_string(config("bitcoind_zmq_block_rpc"))

        if self.network == "testnet":
            self.ip = config("bitcoind_ip_testnet")
            self.rpc_port = config("bitcoind_port_rpc_testnet")
            self.zmq_port = config("bitcoind_zmq_block_port_testnet")
        else:
            self.ip = config("bitcoind_ip_mainnet")
            self.rpc_port = config("bitcoind_port_rpc_mainnet")
            self.zmq_port = config("bitcoind_zmq_block_port_mainnet")

        self.rpc_url = f"http://{self.ip}:{self.rpc_port}"
        self.zmq_url = f"tcp://{self.ip}:{self.zmq_port}"

        self.username = config("bitcoind_user")
        self.pw = config("bitcoind_pw")


bitcoin_config = BitcoinConfig()


class LightningConfig:
    def __init__(self) -> None:
        self.network = config("network")
        self.ln_node = config("ln_node")
        self.cln_sock: "LightningRpc" = None

        if self.ln_node == "lnd_grpc":
            # Due to updated ECDSA generated tls.cert we need to let gprc know that
            # we need to use that cipher suite otherwise there will be a handshake
            # error when we communicate with the lnd rpc server.
            os.environ["GRPC_SSL_CIPHER_SUITES"] = "HIGH+ECDSA"

            # Uncomment to see full gRPC logs
            # os.environ["GRPC_TRACE"] = "all"
            # os.environ["GRPC_VERBOSITY"] = "DEBUG"

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
        elif self.ln_node == "cln_unix_socket":
            self._cln_socket_path = config("cln_socket_path")
            self.cln_sock = LightningRpc(self._cln_socket_path)  # type: LightningRpc
        elif self.ln_node == "cln_grpc":
            cln_grpc_cert = bytes.fromhex(config("cln_grpc_cert"))
            cln_grpc_key = bytes.fromhex(config("cln_grpc_key"))
            cln_grpc_ca = bytes.fromhex(config("cln_grpc_ca"))
            cln_grpc_url = config("cln_grpc_ip") + ":" + config("cln_grpc_port")
            creds = grpc.ssl_channel_credentials(
                root_certificates=cln_grpc_ca,
                private_key=cln_grpc_key,
                certificate_chain=cln_grpc_cert,
            )
            opts = (("grpc.ssl_target_name_override", "cln"),)
            self._channel = grpc.aio.secure_channel(cln_grpc_url, creds, options=opts)
            self.cln_stub = clnrpc.NodeStub(self._channel)
        elif self.ln_node == "":
            # its ok to run raspiblitz also without lightning
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


async def redis_get(key: str) -> str:
    v = await redis_plugin.redis.get(key)

    if not v:
        logging.warning(f"Key '{key}' not found in Redis DB.")
        return ""

    return v.decode("utf-8")


# TODO
# idea is to have a second redis channel called system, that the API subscribes to. If for example
# the 'state' value gets changed by the _cache.sh script, it should publish this to this channel
# so the API can forward the change to thru the SSE to the WebUI


class SSE:
    SYSTEM_INFO = "system_info"
    SYSTEM_SHUTDOWN_NOTICE = "system_shutdown_initiated"
    SYSTEM_SHUTDOWN_ERROR = "system_shutdown_error"
    SYSTEM_REBOOT_NOTICE = "system_reboot_initiated"
    SYSTEM_REBOOT_ERROR = "system_reboot_error"
    HARDWARE_INFO = "hardware_info"

    INSTALL_APP = "install"
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
    LN_FEE_REVENUE = "ln_fee_revenue"
    LN_FORWARD_SUCCESSES = "ln_forward_successes"
    WALLET_BALANCE = "wallet_balance"
    WALLET_LOCK_STATUS = "wallet_lock_status"


# https://gist.github.com/risent/4cab3878d995bec7d1c2
# https://firebase.blog/posts/2015/02/the-2120-ways-to-ensure-unique_68
# https://gist.github.com/mikelehen/3596a30bd69384624c11
class _PushID(object):
    # Modeled after base64 web-safe chars, but ordered by ASCII.
    PUSH_CHARS = (
        "-0123456789" "ABCDEFGHIJKLMNOPQRSTUVWXYZ" "_abcdefghijklmnopqrstuvwxyz"
    )

    def __init__(self):

        # Timestamp of last push, used to prevent local collisions if you
        # pushtwice in one ms.
        self.last_push_time = 0

        # We generate 72-bits of randomness which get turned into 12
        # characters and appended to the timestamp to prevent
        # collisions with other clients.  We store the last characters
        # we generated because in the event of a collision, we'll use
        # those same characters except "incremented" by one.
        self.last_rand_chars = array.array("i", [i for i in range(12)])

    def next_id(self):
        now = int(time.time() * 1000)
        duplicate_time = now == self.last_push_time
        self.last_push_time = now
        time_stamp_chars = array.array("u", "12345678")

        for i in range(7, -1, -1):
            time_stamp_chars[i] = self.PUSH_CHARS[now % 64]
            now = int(now / 64)

        if now != 0:
            raise ValueError("We should have converted the entire timestamp.")

        uid = "".join(time_stamp_chars)

        if not duplicate_time:
            for i in range(12):
                self.last_rand_chars[i] = int(random.random() * 64)
        else:
            # If the timestamp hasn't changed since last push, use the
            # same random number, except incremented by 1.
            for i in range(11, -1, -1):
                if self.last_rand_chars[i] == 63:
                    self.last_rand_chars[i] = 0
                else:
                    break
            self.last_rand_chars[i] += 1

        for i in range(12):
            uid += self.PUSH_CHARS[self.last_rand_chars[i]]

        if len(uid) != 20:
            raise ValueError("Length should be 20.")

        return uid


pid_gen = _PushID()


def next_push_id() -> str:
    """Generates a unique random 20 character long string id

    * They're based on timestamp so that they sort *after* any existing ids.
    * They contain 72-bits of random data after the timestamp so that IDs won't collide with other clients' IDs.
    * They sort *lexicographically* (so the timestamp is converted to characters that will sort properly).
    * They're monotonically increasing.  Even if you generate more than one in the same timestamp, the
      latter ones will sort after the former ones.  We do this by using the previous random bits
      but "incrementing" them by 1 (only in the case of a timestamp collision).
    """
    return pid_gen.next_id()
