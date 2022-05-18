from enum import Enum
from typing import List, Optional

from decouple import config
from fastapi import Query
from fastapi.param_functions import Query
from pydantic import BaseModel
from pydantic.types import constr

from app.routers.system_docs import get_debug_data_sample_str


class LoginInput(BaseModel):
    password: constr(min_length=8)
    one_time_password: Optional[
        constr(min_length=6, max_length=6, regex="^[0-9]+$")
    ] = None


class HealthMessagePriority(str, Enum):
    INFO = "info"  # FYI, can normally be ignored.
    WARNING = (
        "warning"  # Potential problem might occur, user interaction possibly required.
    )
    ERROR = "error"  # Something bad happened. User interaction deinitely required.


class HealthMessage(BaseModel):
    id: int = Query(
        None,
        description="""ID of the message.
Idea behind the ID is that messages can be replacable on the client.
To prevent spamming the user with multiple messages, message with ID 25 will be replaced with never data of ID 25
        """,
        example="""
```{
    id: 25,
    level: "warning",
    message: "HDD is 89.3% full"
}```
    """,
    )

    level: HealthMessagePriority = Query(
        HealthMessagePriority.INFO,
        description="""Priority level of the message. For more info see `message`.

`INFO`:       FYI, can normally be ignored.\n
`WARNING`:    Potential problem might occur, user interaction possibly required.\n
`ERROR`:      Something bad happened. User interaction definitely required.

If there are multiple messages with different priorities, the most severe level will be shown.
        """,
    )
    message: str = Query(..., description="Detailed message description")


class HealthState(str, Enum):
    # All systems work nominally
    GOOD = "good"
    # Some event requires users attention (Software update, HDD nearly full)
    ATTENTION_REQUIRED = "attention_required"
    # An error happened which prevents the node from working properly
    # (Hardware failure, DB corruption, Internet connection not available, ...)
    STOPPED = "stopped"


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
    api_version: str = Query(
        ..., description="Version of the API software on this system."
    )
    health: HealthState = Query(
        ..., description="General health state of the Raspiblitz"
    )
    health_messages: List[HealthMessage] = Query(
        [], description="List of all messages regarding node health."
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
