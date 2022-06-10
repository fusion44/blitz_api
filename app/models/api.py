from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel


class StartupState(str, Enum):
    OFFLINE = "offline"
    BOOTSTRAPPING = "bootstrapping"
    LOCKED = "locked"
    DONE = "done"
    DISABLED = "disabled"


class ApiStartupStatus(BaseModel):
    def __init__(
        __pydantic_self__,
        bitcoin: StartupState = StartupState.OFFLINE,
        bitcoin_msg: Optional[str] = "",
        lightning: StartupState = StartupState.OFFLINE,
        lightning_msg: Optional[str] = "",
    ) -> "ApiStartupStatus":
        super().__init__(
            bitcoin=bitcoin,
            bitcoin_msg=bitcoin_msg,
            lightning=lightning,
            lightning_msg=lightning_msg,
        )

    bitcoin: StartupState
    bitcoin_msg: Optional[str]
    lightning: StartupState
    lightning_msg: Optional[str]

    def is_fully_initialized(self):
        return self.bitcoin == StartupState.DONE and (
            self.lightning == StartupState.DONE
            or self.lightning == StartupState.DISABLED
        )
