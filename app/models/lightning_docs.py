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
