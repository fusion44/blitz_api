from app.auth.auth_bearer import JWTBearer
from app.models.lightning import Invoice
from app.repositories.lightning import add_invoice, get_wallet_balance
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


@router.get("/getwalletbalance", summary="Get the current on chain balances of the lighting wallet.",
            response_description="A JSON String with on chain wallet balances.",
            dependencies=[Depends(JWTBearer())],
            status_code=status.HTTP_200_OK)
async def getwalletbalance():
    try:
        return await get_wallet_balance()
    except HTTPException as r:
        raise HTTPException(r.status_code, detail=r.reason)
    except NotImplementedError as r:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail=r.args[0])
