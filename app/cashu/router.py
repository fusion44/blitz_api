import asyncio
from typing import Union

from fastapi import APIRouter, Body, HTTPException, Query, Response, status

import app.cashu.constants as c
import app.cashu.docs as docs
from app.cashu.errors import CashuException, UntrustedMintException
from app.cashu.models import (
    CashuInfo,
    CashuMint,
    CashuMintInput,
    CashuMintKeyInput,
    CashuPayEstimation,
    CashuReceiveResult,
    CashuWalletBalance,
    CashuWalletData,
)
from app.cashu.service import CashuService

_PREFIX = "cashu"

router = APIRouter(prefix=f"/{_PREFIX}", tags=["Cashu"])
service = CashuService()
loop = asyncio.get_event_loop()
loop.create_task(service.init_wallets())


@router.post(
    "/add-mint",
    name=f"{_PREFIX}.add-mint",
    summary="Adds a mint URL to the known mint database.",
    response_model=CashuMint,
    status_code=status.HTTP_201_CREATED,
    # dependencies=[Depends(JWTBearer())],
)
async def add_mint(mint: CashuMintInput):
    return await service.add_mint(mint)


@router.post(
    "/pin-mint",
    name=f"{_PREFIX}.pin-mint",
    summary=docs.pin_mint_summary,
    description=docs.pin_mint_desc,
    response_model=CashuMint,
    response_description="The url of the mint that was set.",
    # dependencies=[Depends(JWTBearer())],
)
def pin_mint_path(
    url: str = Query(
        c.DEFAULT_MINT_URL,
        description=f"URL of the mint. Will be set to the system default if empty.",
    )
) -> CashuMint:
    try:
        return service.pin_mint(url)
    except HTTPException:
        raise
    except NotImplementedError:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED)


@router.get(
    "/list-mints",
    name=f"{_PREFIX}.list-mints",
    summary="Lists all known mints.",
    response_model=list[CashuMint],
    status_code=status.HTTP_200_OK,
    # dependencies=[Depends(JWTBearer())],
)
async def list_mints():
    try:
        return await service.list_mints()
    except HTTPException:
        raise
    except NotImplementedError:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED)


@router.post(
    "/add-wallet",
    name=f"{_PREFIX}.add-wallet",
    summary="Initializes a new wallet.",
    response_model=CashuWalletData,
    responses={
        status.HTTP_409_CONFLICT: {
            "description": "Wallet already exists.",
        }
    }
    # dependencies=[Depends(JWTBearer())],
)
async def add_wallet_path(
    wallet_name: str = Query(..., min_length=3, description=f"Name of the wallet.")
) -> str:
    try:
        return await service.add_wallet(wallet_name)
    except HTTPException:
        raise
    except NotImplementedError:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED)


@router.post(
    "/pin-wallet",
    name=f"{_PREFIX}.pin-wallet",
    summary=docs.pin_wallet_summary,
    description=docs.pin_wallet_desc,
    response_model=str,
    response_description="The name of the wallet that was set.",
    # dependencies=[Depends(JWTBearer())],
)
def pin_wallet_path(
    wallet_name: str = Query(
        None,
        description=f"Name of the wallet. Will be set to the system default if empty.",
    )
) -> str:
    try:
        return service.pin_wallet(wallet_name)
    except HTTPException:
        raise
    except NotImplementedError:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED)


@router.get(
    "/list-wallets",
    name=f"{_PREFIX}.get-wallets",
    summary="Lists all available Cashu wallets",
    # dependencies=[Depends(JWTBearer())],
)
async def cashu_list_wallets_path(include_balances: bool = False):
    try:
        return await service.list_wallets(include_balances)
    except HTTPException:
        raise
    except NotImplementedError:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED)


@router.get(
    "/get-wallet",
    name=f"{_PREFIX}.get-wallet",
    summary="Get info about a specific Cashu wallet",
    # dependencies=[Depends(JWTBearer())],
)
async def cashu_get_wallet_path(
    mint_name: Union[None, str] = Query(
        None,
        description=f"Name of the mint. Will use the pinned mint if empty.",
    ),
    wallet_name: Union[None, str] = Query(
        None,
        description=f"Name of the wallet. Will use the pinned wallet if empty.",
    ),
    include_balances: bool = False,
):
    try:
        return await service.get_wallet(mint_name, wallet_name, include_balances)
    except HTTPException:
        raise
    except NotImplementedError:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED)


@router.get(
    "/get-balance",
    name=f"{_PREFIX}.get-balance",
    summary=docs.get_balance_summary,
    response_model=CashuWalletBalance
    # dependencies=[Depends(JWTBearer())],
)
def cashu_balance_path():
    try:
        return service.balance()
    except HTTPException:
        raise
    except NotImplementedError:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED)


@router.get(
    "/get-info",
    name=f"{_PREFIX}.get-info",
    summary="Get Cashu environment infos",
    response_model=CashuInfo,
    # dependencies=[Depends(JWTBearer())],
)
def cashu_info_path():
    try:
        return service.info()
    except HTTPException:
        raise
    except NotImplementedError:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED)


@router.post(
    "/mint-tokens",
    name=f"{_PREFIX}.mint-tokens",
    summary="Mint Cashu tokens",
    # dependencies=[Depends(JWTBearer())],
)
async def cashu_mint_path(
    amount: int,
    mint_name: Union[None, str] = Query(
        None,
        description=f"Name of the mint. Will use the pinned mint if empty.",
    ),
    wallet_name: Union[None, str] = Query(
        None,
        description=f"Name of the wallet. Will use the pinned wallet if empty.",
    ),
):
    try:
        return await service.mint(amount, wallet_name, mint_name)
    except HTTPException:
        raise
    except NotImplementedError:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED)


@router.post(
    "/receive-tokens",
    name=f"{_PREFIX}.receive-tokens",
    summary="Receive Cashu tokens",
    response_model=CashuReceiveResult,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "An error happened while receiving the tokens. See the error message for details.",
            "model": CashuReceiveResult,
        },
        status.HTTP_406_NOT_ACCEPTABLE: {
            "description": "The mint is not trusted. Use the /update-mint-key endpoint to trust the mint with the given key.",
            "model": CashuReceiveResult,
        },
    },
    # dependencies=[Depends(JWTBearer())],
)
async def cashu_receive_path(
    response: Response,
    coin: str = Body(..., description="The coins to receive."),
    lock: str = Body(None, description="Unlock coins."),
    wallet_name: Union[None, str] = Body(
        None,
        description=f"Name of the wallet. Will use the pinned wallet if empty.",
    ),
    trust_mint: bool = Body(
        False, description="Automatically trust the mint if it is not trusted yet."
    ),
) -> CashuReceiveResult:
    try:
        return await service.receive(coin, lock, wallet_name, trust_mint)
    except UntrustedMintException as e:
        response.status_code = status.HTTP_406_NOT_ACCEPTABLE
        return CashuReceiveResult.from_exception(e)
    except CashuException as e:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return CashuReceiveResult.from_exception(e)
    except HTTPException:
        raise
    except NotImplementedError:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED)


@router.post(
    "/pay-invoice",
    name=f"{_PREFIX}.pay-invoice",
    summary=docs.pay_invoice_summary,
    description=docs.pay_invoice_description,
    response_model=CashuWalletBalance,
    # dependencies=[Depends(JWTBearer())],
)
async def cashu_pay_path(
    invoice: str = Body(..., description="The coins to receive."),
    mint_name: Union[None, str] = Body(
        None,
        description=f"Name of the mint. Will use the pinned mint if empty.",
    ),
    wallet_name: Union[None, str] = Body(
        None,
        description=f"Name of the wallet. Will use the pinned wallet if empty.",
    ),
) -> CashuWalletBalance:
    try:
        return await service.pay(invoice, wallet_name, mint_name)
    except HTTPException:
        raise
    except NotImplementedError:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED)


@router.post(
    "/estimate-pay",
    name=f"{_PREFIX}.estimate-pay",
    summary=docs.estimate_pay_summary,
    response_model=CashuPayEstimation,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "Zero invoices not allowed. Amount must be positive.",
        }
    }
    # dependencies=[Depends(JWTBearer())],
)
async def cashu_estimate_pay_path(
    invoice: str = Body(
        ...,
        description="The invoice to be estimated",
    ),
    mint_name: Union[None, str] = Body(
        None,
        description=f"Name of the mint. Will use the pinned mint if empty.",
    ),
    wallet_name: Union[None, str] = Body(
        None,
        description=f"Name of the wallet. Will use the pinned wallet if empty.",
    ),
) -> CashuWalletBalance:
    try:
        return await service.estimate_pay(invoice, wallet_name, mint_name)
    except HTTPException:
        raise
    except NotImplementedError:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED)
