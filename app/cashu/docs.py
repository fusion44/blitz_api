pin_mint_summary = "Pins the mint URL. Calling this endpoint with no URL will reset the mint to the system default."
pin_mint_desc = "When calling Cashu endpoints without a mint URL, the system will use the mint URL that was pinned with this endpoint."

pin_wallet_summary = "Pins the current wallet name. Calling this endpoint with no name will reset the wallet to the system default."
pin_wallet_desc = "When calling Cashu endpoints without a wallet name, the system will use the wallet that was pinned with this endpoint."

get_balance_summary = "Get the combined balance of all the known Cashu wallets. To get balances of single wallets use the /list-wallets endpoint."

estimate_pay_summary = "Decodes the amount from a Lightning invoice and returns the total amount (amount+fees) to be paid."

pay_invoice_summary = (
    "Pay a lightning invoice via available tokens on a mint or a lightning payment."
)


pay_invoice_description = """
This endpoint will try to pay the invoice using the available tokens on the mint.
If it fails it will try to pay the invoice using a lightning payment.

> 👉 This is different from the /lightning/pay-invoice endpoint which will only try to pay the invoice using a lightning payment.
"""
