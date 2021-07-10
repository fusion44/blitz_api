import os

import app.repositories.ln_impl.protos.rpc_pb2 as ln
import app.repositories.ln_impl.protos.rpc_pb2_grpc as lnrpc
import grpc
from app.utils import lightning_config as lncfg

# Due to updated ECDSA generated tls.cert we need to let gprc know that
# we need to use that cipher suite otherwise there will be a handshake
# error when we communicate with the lnd rpc server.
os.environ["GRPC_SSL_CIPHER_SUITES"] = 'HIGH+ECDSA'

# Uncomment to see full gRPC logs
# os.environ["GRPC_TRACE"] = 'all'
# os.environ["GRPC_VERBOSITY"] = 'DEBUG'

_creds = grpc.ssl_channel_credentials(lncfg.lnd_cert)
_channel = grpc.secure_channel(lncfg.lnd_grpc_url, _creds)
ln_stub = lnrpc.LightningStub(_channel)


def get_wallet_balance_impl() -> object:
    response = ln_stub.WalletBalance(
        ln.WalletBalanceRequest(),
        metadata=[('macaroon', lncfg.lnd_macaroon)],
    )

    return {
        "confirmed_balance": response.confirmed_balance,
        "total_balance": response.total_balance,
        "unconfirmed_balance": response.unconfirmed_balance,
    }
