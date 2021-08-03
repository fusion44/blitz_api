from app.auth.auth_bearer import JWTBearer
from app.models.lightning import Invoice, LnInfo, Payment, WalletBalance
from app.repositories.lightning import (add_invoice, get_ln_info,
                                        get_wallet_balance, send_payment)
from app.routers.lightning_docs import send_payment_desc
from fastapi import APIRouter, HTTPException, status
from fastapi.params import Depends

router = APIRouter(
    prefix="/lightning",
    tags=["Lightning"]
)


@router.post("/addinvoice", summary="Addinvoice adds a new Invoice to the database.",
             description="For additional information see [LND docs](https://api.lightning.community/#addinvoice)",
             dependencies=[Depends(JWTBearer())],
             status_code=status.HTTP_200_OK,
             response_model=Invoice)
async def addinvoice(value_msat: int, memo: str = "", expiry: int = 3600, is_keysend: bool = False):
    try:
        return await add_invoice(memo, value_msat, expiry, is_keysend)
    except HTTPException as r:
        raise HTTPException(r.status_code, detail=r.reason)
    except NotImplementedError as r:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail=r.args[0])


@router.get("/getbalance", summary="Get the current on chain and channel balances of the lighting wallet.",
            response_description="A JSON String with on chain wallet balances.",
            dependencies=[Depends(JWTBearer())],
            status_code=status.HTTP_200_OK,
            response_model=WalletBalance)
async def getwalletbalance():
    try:
        return await get_wallet_balance()
    except HTTPException as r:
        raise HTTPException(r.status_code, detail=r.reason)
    except NotImplementedError as r:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail=r.args[0])


@router.post("/sendpayment", summary="Attempt to pay a payment request.",
             description=send_payment_desc,
             response_description="Either an error or a Payment object on success",
             dependencies=[Depends(JWTBearer())],
             status_code=status.HTTP_200_OK,
             response_model=Payment)
async def sendpayment(pay_req: str, timeout_seconds: int = 5, fee_limit_msat: int = 8000):
    try:
        return await send_payment(pay_req, timeout_seconds, fee_limit_msat)
    except HTTPException as r:
        raise HTTPException(r.status_code, detail=r.detail)
    except NotImplementedError as r:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail=r.args[0])


@router.get("/getinfo", summary="Request information about the currently running lightning node.",
            response_description="Either an error or a LnInfo object on success",
            dependencies=[Depends(JWTBearer())],
            status_code=status.HTTP_200_OK,
            response_model=LnInfo)
async def get_info():
    try:
        return await get_ln_info()
    except HTTPException as r:
        raise HTTPException(r.status_code, detail=r.detail)
    except NotImplementedError as r:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail=r.args[0])
