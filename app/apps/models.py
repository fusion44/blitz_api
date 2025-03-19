from enum import Enum
from typing import List, Optional

from fastapi import Query
from pydantic.main import BaseModel

from app.api.error_report.report import Report
from app.external.result_type.src.result import Err, Ok, Result


class AppOnlineStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"


class AppId(str, Enum):
    ALBYHUB = "albyhub"
    BTCPAYSERVER = "btcpayserver"
    BTC_RPC_EXPLORER = "btc-rpc-explorer"
    ELECTRS = "electrs"
    JAM = "jam"
    LNBITS = "lnbits"
    MEMPOOL = "mempool"
    RTL = "rtl"
    THUNDERHUB = "thunderhub"

    @staticmethod
    def as_str_list() -> List[str]:
        return [app_id.value for app_id in AppId]

    @staticmethod
    def from_str(label: str) -> Result["AppId", Report]:
        try:
            return Ok(AppId(label))
        except ValueError:
            return Err(Report(f"'{label}' is not a valid AvailableAppId"))


class AppStatus(BaseModel):
    id: AppId = Query(..., description="Id of the applications")
    version: Optional[str] = Query(None, description="Version of the application")
    installed: bool = Query(False, description="Whether the application is installed")
    configured: bool = Query(False, description="Whether the application is configured")
    status: AppOnlineStatus = Query(
        AppOnlineStatus.OFFLINE, description="Whether the application is online"
    )
    local_ip: Optional[str] = Query(
        None, description="The local network IP of the application"
    )
    http_port: Optional[str] = Query(
        None, description="The http port of the application"
    )
    https_port: Optional[str] = Query(
        None, description="The https port of the application"
    )
    https_forced: Optional[bool] = Query(
        None, description="Whether https is forced for this application"
    )
    https_self_signed: Optional[bool] = Query(
        None, description="Whether the https certificate is self signed"
    )
    hidden_service: Optional[str] = Query(
        None,
        description="Whether the application is reachable via a tor hidden service",
    )
    address: Optional[str] = Query(
        None, description="The full address where this application is reachable"
    )
    auth_method: Optional[str] = Query(
        None, description="The authentication method this application uses"
    )
    details: Optional[dict] = Query(
        None,
        description=f"""Additional application specific details

        This field can contain values for the following app ids:
        - `{AppId.MEMPOOL.value}`: `is_indexed`, `index_info`
        - `{AppId.BTC_RPC_EXPLORER.value}`: `is_indexed`, `index_info`
        - `{AppId.ELECTRS.value}`: `initial_sync_done`, `block_height`,
                                   `blockheightPercent`, `info_sync`,
                                   `electrum_responding`,
        """,
    )
    error: Optional[str] = Query(
        None, description="Last known encountered error for this app."
    )


class AppStatusQueryError(BaseModel):
    id: AppId = Query(..., description="The app id")
    error: str = Query(..., description="The error description")


class AppStatusQueryResult(BaseModel):
    data: List[AppStatus] = Query(
        [], description="Contains the successfully queried app statuses"
    )
    errors: List[AppStatusQueryError] = Query(
        [], description="Contains the error messages for unsuccessful queries"
    )


class UninstallData(BaseModel):
    keepData: bool = True
