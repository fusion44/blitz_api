from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.params import Depends

from app.auth.auth_bearer import JWTBearer
from app.lightning.docs import (
    get_balance_response_desc,
    new_address_desc,
    open_channel_desc,
    send_coins_desc,
    send_payment_desc,
    unlock_wallet_desc,
)
from app.lightning.models import (
    Channel,
    FeeRevenue,
    GenericTx,
    Invoice,
    LightningInfoLite,
    LnInfo,
    NewAddressInput,
    OnChainTransaction,
    Payment,
    PaymentRequest,
    SendCoinsInput,
    SendCoinsResponse,
    UnlockWalletInput,
    WalletBalance,
)
from app.lightning.service import (
    add_invoice,
    channel_close,
    channel_list,
    channel_open,
    decode_pay_request,
    get_fee_revenue,
    get_ln_info,
    get_ln_info_lite,
    get_wallet_balance,
    list_all_tx,
    list_invoices,
    list_on_chain_tx,
    list_payments,
    new_address,
    send_coins,
    send_payment,
    unlock_wallet,
)

_PREFIX = "lightning"

router = APIRouter(prefix=f"/{_PREFIX}", tags=["Lightning"])

responses = {
    423: {
        "description": "LND only: Wallet is locked. Unlock via /lightning/unlock-wallet."
    }
}


@router.post(
    "/add-invoice",
    name=f"{_PREFIX}.add-invoice",
    summary="Addinvoice adds a new Invoice to the database.",
    description="For additional information see [LND docs](https://api.lightning.community/#addinvoice)",
    dependencies=[Depends(JWTBearer())],
    response_model=Invoice,
    responses=responses,
)
async def addinvoice(
    value_msat: int, memo: str = "", expiry: int = 3600, is_keysend: bool = False
):
    try:
        return await add_invoice(memo, value_msat, expiry, is_keysend)
    except HTTPException as r:
        raise
    except NotImplementedError as r:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail=r.args[0])


@router.get(
    "/get-balance",
    name=f"{_PREFIX}.get-balance",
    summary="Get the current on chain and channel balances of the lighting wallet.",
    response_description=get_balance_response_desc,
    dependencies=[Depends(JWTBearer())],
    response_model=WalletBalance,
    responses=responses,
)
async def getwalletbalance():
    try:
        return await get_wallet_balance()
    except HTTPException as r:
        raise
    except NotImplementedError as r:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail=r.args[0])


@router.get(
    "/get-fee-revenue",
    name=f"{_PREFIX}.get-fee-revenue",
    summary="Returns the daily, weekly and monthly fee revenue earned.",
    description="""
Currently, year and total fees are always null. Backends don't return these values by default.
Implementation in BlitzAPI is a [to-do](https://github.com/fusion44/blitz_api/issues/64).
    """,
    dependencies=[Depends(JWTBearer())],
    response_model=FeeRevenue,
    responses=responses,
)
async def get_fee_revenue_path() -> FeeRevenue:
    try:
        return await get_fee_revenue()
    except HTTPException as r:
        raise
    except NotImplementedError as r:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail=r.args[0])


@router.get(
    "/list-all-tx",
    name=f"{_PREFIX}.list-all-tx",
    summary="Lists all on-chain transactions, payments and invoices in the wallet",
    description="""Returns a list with all on-chain transaction, payments and invoices combined into one list.
    The index of each tx is only valid for each identical set of parameters.
    """,
    dependencies=[Depends(JWTBearer())],
    response_model=List[GenericTx],
    responses=responses,
)
async def list_all_tx_path(
    successful_only: bool = Query(
        False,
        description="If set, only successful transaction will be returned in the response.",
    ),
    index_offset: int = Query(
        0,
        description="The index of an transaction that will be used as either the start or end of a query to determine which invoices should be returned in the response.",
    ),
    max_tx: int = Query(
        0,
        description="The max number of transaction to return in the response to this query. Will return all transactions when set to 0 or null.",
    ),
    reversed: bool = Query(
        False,
        description="If set, the transactions returned will result from seeking backwards from the specified index offset. This can be used to paginate backwards.",
    ),
):
    try:
        return await list_all_tx(successful_only, index_offset, max_tx, reversed)
    except HTTPException as r:
        raise
    except NotImplementedError as r:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail=r.args[0])


@router.get(
    "/list-invoices",
    name=f"{_PREFIX}.list-invoices",
    summary="Lists all invoices from the wallet. Modeled after LND implementation.",
    response_model=List[Invoice],
    response_description="A list of all invoices created.",
    dependencies=[Depends(JWTBearer())],
    responses=responses,
)
async def list_invoices_path(
    pending_only: bool = Query(
        False,
        description="If set, only invoices that are not settled and not canceled will be returned in the response.",
    ),
    index_offset: int = Query(
        0,
        description="The index of an invoice that will be used as either the start or end of a query to determine which invoices should be returned in the response.",
    ),
    num_max_invoices: int = Query(
        0,
        description="The max number of invoices to return in the response to this query. Will return all invoices when set to 0 or null.",
    ),
    reversed: bool = Query(
        False,
        description="If set, the invoices returned will result from seeking backwards from the specified index offset. This can be used to paginate backwards.",
    ),
):
    try:
        return await list_invoices(
            pending_only,
            index_offset,
            num_max_invoices,
            reversed,
        )
    except HTTPException as r:
        raise
    except NotImplementedError as r:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail=r.args[0])


@router.get(
    "/list-onchain-tx",
    name=f"{_PREFIX}.list-onchain-tx",
    summary="Lists all onchain transactions from the wallet",
    response_model=List[OnChainTransaction],
    response_description="A list of all on-chain transactions made.",
    dependencies=[Depends(JWTBearer())],
    responses=responses,
)
async def list_on_chain_tx_path():
    try:
        return await list_on_chain_tx()
    except HTTPException as r:
        raise
    except NotImplementedError as r:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail=r.args[0])


@router.get(
    "/list-payments",
    name=f"{_PREFIX}.list-payments",
    summary="Returns a list of all outgoing payments. Modeled after LND implementation.",
    response_model=List[Payment],
    response_description="A list of all payments made.",
    dependencies=[Depends(JWTBearer())],
    responses=responses,
)
async def list_payments_path(
    include_incomplete: bool = Query(
        True,
        description="If true, then return payments that have not yet fully completed. This means that pending payments, as well as failed payments will show up if this field is set to true. This flag doesn't change the meaning of the indices, which are tied to individual payments.",
    ),
    index_offset: int = Query(
        0,
        description="The index of a payment that will be used as either the start or end of a query to determine which payments should be returned in the response. The index_offset is exclusive. In the case of a zero index_offset, the query will start with the oldest payment when paginating forwards, or will end with the most recent payment when paginating backwards.",
    ),
    max_payments: int = Query(
        0,
        description="The maximal number of payments returned in the response to this query.",
    ),
    reversed: bool = Query(
        False,
        description="If set, the payments returned will result from seeking backwards from the specified index offset. This can be used to paginate backwards. The order of the returned payments is always oldest first (ascending index order).",
    ),
):
    try:
        return await list_payments(
            include_incomplete, index_offset, max_payments, reversed
        )
    except HTTPException as r:
        raise
    except NotImplementedError as r:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail=r.args[0])


@router.post(
    "/new-address",
    name=f"{_PREFIX}.new-address",
    summary="Generate a new on-chain address",
    description=new_address_desc,
    response_description="The newly generated wallet address",
    dependencies=[Depends(JWTBearer())],
    response_model=str,
    responses=responses,
)
async def new_address_path(input: NewAddressInput):
    try:
        return await new_address(input)
    except HTTPException as r:
        raise
    except NotImplementedError as r:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail=r.args[0])


@router.post(
    "/send-coins",
    name=f"{_PREFIX}.send-coins",
    summary="Attempt to send on-chain funds.",
    description=send_coins_desc,
    response_description="Either an error or a SendCoinsResponse object on success",
    dependencies=[Depends(JWTBearer())],
    response_model=SendCoinsResponse,
    responses={
        412: {"description": "When not enough funds are available."},
        423: responses[423],
    },
)
async def send_coins_path(input: SendCoinsInput):
    try:
        return await send_coins(input=input)
    except HTTPException as r:
        raise
    except NotImplementedError as r:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail=r.args[0])


@router.post(
    "/open-channel",
    name=f"{_PREFIX}.open-channel",
    summary="open a new lightning channel",
    description=open_channel_desc,
    dependencies=[Depends(JWTBearer())],
    response_model=str,
    responses={
        412: {"description": "When not enough funds are available."},
        423: responses[423],
        504: {"description": "When the peer is not reachable."},
    },
)
async def open_channel_path(
    local_funding_amount: int, node_URI: str, target_confs: int = 3
):
    try:
        return await channel_open(local_funding_amount, node_URI, target_confs)
    except HTTPException as r:
        raise
    except NotImplementedError as r:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail=r.args[0])
    except ValueError as r:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=r.args[0])


@router.get(
    "/list-channels",
    name=f"{_PREFIX}.list-channels",
    summary="Returns a list of open channels",
    response_model=List[Channel],
    response_description="A list of all open channels.",
    dependencies=[Depends(JWTBearer())],
    responses=responses,
)
async def list_channels_path():
    try:
        return await channel_list()
    except HTTPException as r:
        raise
    except NotImplementedError as r:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail=r.args[0])
    except ValueError as r:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=r.args[0])


@router.post(
    "/close-channel",
    name=f"{_PREFIX}.close-channel",
    summary="close a channel",
    description="For additional information see [LND docs](https://api.lightning.community/#closechannel)",
    dependencies=[Depends(JWTBearer())],
    response_model=str,
    responses=responses,
)
async def close_channel_path(channel_id: str, force_close: bool):
    try:
        return await channel_close(channel_id, force_close)
    except HTTPException as r:
        raise
    except NotImplementedError as r:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail=r.args[0])
    except ValueError as r:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=r.args[0])


@router.post(
    "/send-payment",
    name=f"{_PREFIX}.send-payment",
    summary="Attempt to pay a payment request.",
    description=send_payment_desc,
    response_description="Either an error or a Payment object on success",
    dependencies=[Depends(JWTBearer())],
    response_model=Payment,
    responses={
        400: {
            "description": """
Possible error messages:
* invalid bech32 string
* amount must be specified when paying a zero amount invoice
* amount must not be specified when paying a non-zero amount invoice
"""
        },
        409: {
            "description": "[LND only] When attempting to pay an already paid invoice. CLN will return the payment object of the previously paid invoice. Info: [GitHub](https://github.com/fusion44/blitz_api/issues/131)",
        },
        423: responses[423],
    },
)
async def sendpayment(
    pay_req: str,
    timeout_seconds: int = 5,
    fee_limit_msat: int = 8000,
    amount_msat: Optional[int] = None,
):
    try:
        return await send_payment(pay_req, timeout_seconds, fee_limit_msat, amount_msat)
    except HTTPException as r:
        raise
    except NotImplementedError as r:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail=r.args[0])


@router.get(
    "/get-info",
    name=f"{_PREFIX}.get-info",
    summary="Request information about the currently running lightning node.",
    response_description="Either an error or a LnInfo object on success",
    dependencies=[Depends(JWTBearer())],
    response_model=LnInfo,
    responses=responses,
)
async def get_info():
    try:
        return await get_ln_info()
    except HTTPException as r:
        raise
    except NotImplementedError as r:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail=r.args[0])


@router.get(
    "/get-info-lite",
    name=f"{_PREFIX}.get-info-lite",
    summary="Get lightweight current lightning info. Less verbose version of /lightning/get-info",
    dependencies=[Depends(JWTBearer())],
    status_code=status.HTTP_200_OK,
    response_model=LightningInfoLite,
    responses=responses,
)
async def get_ln_info_lite_path():
    try:
        return await get_ln_info_lite()
    except HTTPException as r:
        raise
    except NotImplementedError as r:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail=r.args[0])


@router.get(
    "/decode-pay-req",
    name=f"{_PREFIX}.decode-pay-req",
    summary="DecodePayReq takes an encoded payment request string and attempts to decode it, returning a full description of the conditions encoded within the payment request.",
    response_model=PaymentRequest,
    response_description="A fully decoded payment request or a HTTP status 400 if the payment request cannot be decoded.",
    dependencies=[Depends(JWTBearer())],
    responses=responses,
)
async def get_decode_pay_request(
    pay_req: str = Query(..., description="The payment request string to be decoded")
):
    try:
        return await decode_pay_request(pay_req)
    except HTTPException as r:
        raise
    except NotImplementedError as r:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail=r.args[0])


@router.post(
    "/unlock-wallet",
    name=f"{_PREFIX}.unlock-wallet",
    summary="Unlocks a locked wallet.",
    response_model=bool,
    response_description=unlock_wallet_desc,
    dependencies=[Depends(JWTBearer())],
    responses={
        401: {
            "description": "Either JWT token is not ok OR wallet password is wrong, observe the detail message."
        },
        412: {"description": "Wallet already unlocked"},
    },
)
async def unlock_wallet_path(input: UnlockWalletInput) -> bool:
    try:
        return await unlock_wallet(input.password)
    except HTTPException as r:
        raise
    except NotImplementedError as r:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail=r.args[0])
