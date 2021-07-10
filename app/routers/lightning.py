from app.auth.auth_bearer import JWTBearer
from app.repositories.lightning import get_wallet_balance
from fastapi import APIRouter, HTTPException, status
from fastapi.params import Depends

router = APIRouter(
    prefix="/lightning",
    tags=["Lightning"]
)


@router.get("/getwalletbalance", summary="Get the current on chain balances of the lighting wallet.",
            response_description="A JSON String with on chain wallet balances.",
            dependencies=[Depends(JWTBearer())],
            status_code=status.HTTP_200_OK)
def getwalletbalance():
    try:
        return get_wallet_balance()
    except HTTPException as r:
        raise HTTPException(r.status_code, detail=r.reason)
    except NotImplementedError as r:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail=r.args[0])
