add_invoice_desc = """
Adds a new invoice to the database.

LND is generating a unique auto-incrementing `add_index` for the invoice.

CLN will receive a [Firebase-like PushID](https://firebase.blog/posts/2015/02/the-2120-ways-to-ensure-unique_68) from the backend for the `label` when creating the invoice.

Please refer to the response schema docs for more information.
"""

get_balance_response_desc = """
A JSON String with on chain wallet balances with on-chain balances in
**sat** and channel balances in **msat**. Detailed description is in
the schema"""

new_address_desc = """
Generate a wallet new address. Address-types has to be one of:
* **p2wkh**:  Pay to witness key hash (bech32)
* **np2wkh**: Pay to nested witness key hash
    """

send_coins_desc = """
__send-coins__ executes a request to send coins to a particular address.

### LND:
If neither __target_conf__, or __sat_per_vbyte__ are set, then the internal wallet will consult its fee model to determine a fee for the default confirmation target.

> 👉 See [https://api.lightning.community/?shell#sendcoins](https://api.lightning.community/?shell#sendcoins)

### c-lightning:
* Set __target_conf__ ==1: interpreted as urgent (aim for next block)
* Set __target_conf__ >=2: interpreted as normal (next 4 blocks or so, **default**)
* Set __target_cont__ >=10: interpreted as slow (next 100 blocks or so)
* If __sat_per_vbyte__ is set then __target_conf__ is ignored and vbytes (sipabytes) will be used.

> 👉 See [https://lightning.readthedocs.io/lightning-txprepare.7.html](https://lightning.readthedocs.io/lightning-txprepare.7.html)
"""

send_payment_desc = """
This endpoints attempts to pay a payment request.

Intermediate status updates will be sent via the SSE channel. This endpoint returns the last success or error message from the node.
"""

open_channel_desc = """
__open-channel__ attempts to open a channel with a peer.

### LND:
_target_conf_: The target number of blocks that the funding transaction should be confirmed by.

### c-lightning:
* Set _target_conf_ ==1: interpreted as urgent (aim for next block)
* Set _target_conf_ >=2: interpreted as normal (next 4 blocks or so, **default**)
* Set _target_cont_ >=10: interpreted as slow (next 100 blocks or so)

> 👉 See [https://lightning.readthedocs.io/lightning-txprepare.7.html](https://lightning.readthedocs.io/lightning-txprepare.7.html)
"""

unlock_wallet_desc = """
`True` if ok, `False` otherwise

### LND:
This call will wait until the LND daemon is fully ready to accept calls. Internally it'll call GetInfo every
0.1 seconds and returns True for the first successful call.

> ℹ️ _After the unlock the LND-gRPC server takes a bit of time to boot up._

### Core Lightning:

> ℹ️ _Platform: Native_ CLN doesn't support wallet locking and will return True immediately.

> ℹ️ _Platform: RaspiBlitz_ RaspiBlitz has its own locking implementation on top of CLN. Will unlock and return True if successful. Might take a few seconds. If it takes longer than 60 seconds it'll return an error.
"""
