from fastapi import APIRouter, HTTPException, status, Request
from fastapi.params import Depends

from app.utils import bitcoin_rpc
from app.auth.auth_bearer import JWTBearer

router = APIRouter(
    prefix="/bitcoin",
    tags=["Bitcoin Core"]
)


@router.get("/getblockcount", summary="Get the current block count",
            description="See documentation on [bitcoincore.org](https://bitcoincore.org/en/doc/0.21.0/rpc/blockchain/getblockcount/)",
            response_description="""A JSON String with relevant information.\n
```json
{
  \"result\": 682621,
  \"error\": null,
  \"id\": 0
}
""",
            dependencies=[Depends(JWTBearer())],
            status_code=status.HTTP_200_OK)
def getblockcount():
    r = bitcoin_rpc("getblockcount")

    if(r.status_code == status.HTTP_200_OK):
        return r.content
    else:
        raise HTTPException(r.status_code, detail=r.reason)


@router.get("/getblockchaininfo", summary="Get the current blockchain status",
            description="See documentation on [bitcoincore.org](https://bitcoincore.org/en/doc/0.21.0/rpc/blockchain/getblockchaininfo/)",
            response_description="A JSON String with relevant information.",
            dependencies=[Depends(JWTBearer())],
            status_code=status.HTTP_200_OK)
def getblockchaininfo():
    r = bitcoin_rpc("getblockchaininfo")

    if(r.status_code == status.HTTP_200_OK):
        return r.content
    else:
        raise HTTPException(r.status_code, detail=r.reason)
