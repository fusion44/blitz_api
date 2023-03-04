from enum import Enum
from typing import Optional

from decouple import config
from fastapi import Query
from fastapi.param_functions import Query
from pydantic import BaseModel
from pydantic.types import constr

from app.system.docs import get_debug_data_sample_str


class LoginInput(BaseModel):
    password: constr(min_length=8)
    one_time_password: Optional[
        constr(min_length=6, max_length=6, regex="^[0-9]+$")
    ] = None


class APIPlatform(str, Enum):
    RASPIBLITZ = "raspiblitz"
    NATIVE_PYTHON = "native_python"
    UNKNOWN = "unknown"

    @staticmethod
    def get_current():
        p = config("platform", default="raspiblitz")
        if p == "raspiblitz":
            return APIPlatform.RASPIBLITZ
        elif p == "native_python":
            return APIPlatform.NATIVE_PYTHON
        else:
            return APIPlatform.UNKNOWN


class SystemInfo(BaseModel):
    alias: str = Query("", description="Name of the node (same as Lightning alias)")
    color: str = Query(
        ..., description="The color of the current node in hex code format"
    )
    platform: APIPlatform = Query(
        APIPlatform.RASPIBLITZ,
        description="The platform this API is running on.",
    )
    platform_version: str = Query(
        "",
        description="The version of this platform",
    )
    code_version = Query(
        "",
        description="[RaspiBlitz only] The code version.",
    )
    api_version: str = Query(
        ..., description="Version of the API software on this system."
    )
    tor_web_ui: str = Query("", description="WebUI TOR address")
    tor_api: str = Query("", description="API TOR address")
    lan_web_ui: str = Query("", description="WebUI LAN address")
    lan_api: str = Query("", description="API LAN address")
    ssh_address: str = Query(
        ...,
        description="Address to ssh into on local LAN (e.g. `ssh admin@192.168.1.28`",
    )
    # This is here to avoid having duplicated entries in BtcStatus and LnStatus
    # The chain status will always be the same between Bitcoin Core
    # and the Lightning Implementation
    chain: str = Query(
        ...,
        description="The current chain this node is connected to (mainnet, testnet or signet)",
    )


class RawDebugLogData(BaseModel):
    raw_data: str = Query(
        ..., description="The raw debug log text", example=get_debug_data_sample_str
    )
    github_issues_url: str = Query(
        "https://www.github.com/rootzoll/raspiblitz/issues",
        description="Link to the Raspiblitz issue tracker",
    )


class ConnectionInfo(BaseModel):
    lnd_admin_macaroon: str = Query(
        "", description="lnd macaroon with admin rights in hexstring format"
    )
    lnd_invoice_macaroon: str = Query(
        "", description="lnd macaroon that only creates invoices in hexstring format"
    )
    lnd_readonly_macaroon: str = Query(
        "", description="lnd macaroon with only read-only rights in hexstring format"
    )
    lnd_tls_cert: str = Query("", description="lnd tls cert in hexstring format")
    lnd_rest_onion: str = Query("", description="lnd rest api onion address")

    lnd_btcpay_connection_string: str = Query(
        "", description="connect BtcPay server locally to your lnd lightning node"
    )
    lnd_zeus_connection_string: str = Query(
        "", description="connect Zeus app to your lnd lightning node"
    )

    cl_rest_zeus_connection_string: str = Query(
        "", description="connect Zeus app to your core lightning node over rest"
    )
    cl_rest_macaroon: str = Query("", description="core lightning rest macaroon")
    cl_rest_onion: str = Query("", description="core lightning rest onion address")
