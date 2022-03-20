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
