from fastapi import APIRouter, HTTPException, status
from fastapi.params import Depends

from app.auth.auth_handler import signJWT
from app.auth.auth_bearer import JWTBearer

router = APIRouter(
    prefix="/system",
    tags=["System"]
)


@router.post("/login", summary="Logs the user in with password A",
             response_description="JWT token for the current session.")
def login(password_a: str):
    if password_a == "123":
        return signJWT()

    raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                        detail="Password is wrong")


@router.get("/temperatures", dependencies=[Depends(JWTBearer())])
def get_temperatures():
    return "45 °C"
