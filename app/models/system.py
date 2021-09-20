from enum import Enum
from typing import List, Optional

from app.models.lightning import LnInfo
from app.routers.system_docs import get_debug_data_sample_str
from fastapi import Query
from fastapi.param_functions import Query
from pydantic import BaseModel
from pydantic.types import constr


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


class SystemInfo(BaseModel):
    alias: str = Query("", description="Name of the node (same as Lightning alias)")
    color: str = Query(
        ..., description="The color of the current node in hex code format"
    )
    version: str = Query(..., description="The software version of this RaspiBlitz")
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

    @classmethod
    def from_rpc(cls, lninfo: LnInfo):
        # TODO: implement rest of the calls
        return cls(
            alias=lninfo.alias,
            color=lninfo.color,
            version="v1.8.0",
            health=HealthState.ATTENTION_REQUIRED,
            health_messages=[
                HealthMessage(
                    id=25, level=HealthMessagePriority.WARNING, message="HDD 85% full"
                )
            ],
            tor_web_ui="arg6ybal4b7dszmsncsrudcpdfkxadzfdi24ktceodah7tgmdopgpyfd.onion",
            tor_api="arg6ybal4b7dszmsncsrudcpdfkxadzfdi24ktceodah7tgmdopgpyfd.onion/api",
            lan_web_ui="http://192.168.1.12/",
            lan_api="http://192.168.1.12/api",
            ssh_address="http://192.168.1.12/",
            chain=lninfo.chains[
                0
            ].network,  # for now, assume we are only on bitcoin chain
        )


class RawDebugLogData(BaseModel):
    raw_data: str = Query(
        ..., description="The raw debug log text", example=get_debug_data_sample_str
    )
    github_issues_url: str = Query(
        "https://www.github.com/rootzoll/raspiblitz/issues",
        description="Link to the Raspiblitz issue tracker",
    )
