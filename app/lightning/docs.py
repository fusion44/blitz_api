tx_id_desc = """
Unique identifier for this transaction.

Depending on the type of the transaction it will be different:
#### On-chain
The transaction hash

#### Lightning Invoice and Payment
The payment request
"""

tx_amount_desc = """
The value of the transaction, depending on the category in satoshis or millisatoshis.

#### On-chain
Transaction amount in satoshis

#### Lightning Invoice
* value in millisatoshis of the invoice if *unsettled*
* amount in millisatoshis paid if invoice is *settled*

#### Lightning Payment
* amount sent in millisatoshis

"""

tx_status_desc = """
The status of the transaction. Depending on the transaction category this can be different values:

May have different meanings in different situations:
#### unknown
An unknown state was found.

#### in_flight
* A lightning payment is being sent
* An invoice is waiting for the incoming payment
* An on-chain transaction is waiting in the mempool

#### succeeded
* A lighting payment was successfully sent
* An incoming payment was received for an invoice
* An on-chain transaction was included in a block

#### failed
* A lightning payment attempt which could not be completed (no route found, insufficient funds, ...)
* An invoice is expired or some other error happened
"""

tx_time_stamp_desc = """
The unix timestamp in seconds for the transaction.

The timestamp can mean different things in different situations:

#### Lightning Invoice
* Creation date for in-flight or failed invoices
* Settle date for succeeded invoices

#### On-chain
* Creation date for transaction waiting in the mempool
* Timestamp of the block where this transaction is included

#### Lightning Payment

"""

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

### Sending all onchain funds
> ℹ️ Keep the following points in mind when sending all onchain funds:

* If __send_all__ is set to __true__, the __amount__ field must be set to __0__.
* If the __amount__ field is greater than __0__, the __send_all__ field must be __false__.
  * The API will return an error if neither or both conditions are met at the same time.
* If __send_all__ is set to __true__ the amount of satoshis to send will be calculated by subtracting the fee from the wallet balance.
* If the wallet balance is not sufficient to cover the fee, the call will fail.
* The call will __not__ close any channels.
* The implementation may keep a reserve of funds if there are still open channels.
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
