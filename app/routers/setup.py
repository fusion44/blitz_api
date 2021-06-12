from fastapi import APIRouter, HTTPException, status
from fastapi.params import Depends

from app.auth.auth_bearer import JWTBearer

router = APIRouter(
    prefix="/setup",
    tags=["Setup"]
)


@router.get("/status", dependencies=[Depends(JWTBearer())])
def get_status():
    return HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)
