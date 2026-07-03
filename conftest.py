"""
Test environment defaults.

The application reads its configuration via python-decouple at import time,
so these variables must be set before any `app.*` module is imported.
Real environment variables take precedence (os.environ.setdefault).
"""

import os

_TEST_ENV_DEFAULTS = {
    "BAPI_PLATFORM": "native_python",
    "BAPI_LN_NODE": "lnd_grpc",
    "BAPI_JWT_SECRET": "test_secret",
    "BAPI_JWT_ALGORITHM": "HS256",
    "BAPI_NETWORK": "regtest",
    "BAPI_BITCOIND_ADDRESS": "127.0.0.1",
    "BAPI_BITCOIND_PORT_RPC": "18443",
    "BAPI_BITCOIND_USER": "test",
    "BAPI_BITCOIND_RPC_PW": "test",
    "BAPI_BITCOIND_ZMQ_BLOCK_RPC": "hashblock",
    "BAPI_BITCOIND_ZMQ_BLOCK_PORT": "28332",
}

for _key, _value in _TEST_ENV_DEFAULTS.items():
    os.environ.setdefault(_key, _value)
