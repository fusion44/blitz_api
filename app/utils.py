import requests
import json
from decouple import config

BITCOIND_IP = config("bitcoind_ip")
BITCOIND_PORT = config("bitcoind_port")
BITCOIND_USER = config("bitcoind_user")
BITCOIND_PW = config("bitcoind_pw")


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
    url = f"http://{BITCOIND_IP}:{BITCOIND_PORT}"
    auth = (BITCOIND_USER, BITCOIND_PW)
    headers = {"Content-type": "text/plain"}
    data = '{"jsonrpc": "2.0", "method": "' + \
        method + '", "id":"0", "params":' + json.dumps(params) + '}'
    return requests.post(url, auth=auth, headers=headers, data=data)
