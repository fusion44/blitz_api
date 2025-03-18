from enum import Enum

from typing import Optional, Union, Dict, List, Sequence, Any

from pydantic import BaseModel
from fastapi import Query


class ApiErrors(str, Enum):
    INVALID_REQUEST_INPUT = "invalid_request_input"
    UNABLE_TO_PROCESS_ERROR = "unable_to_process_error"


class ErrorMessage(BaseModel):
    detail: str = Query(..., description="short text representation of the error")
    error_code: str = Query("", description="a unique identifier for the error")
    report: Optional[Union[str, Dict, List, Sequence[Any]]] = Query(
        None,
        description="optional more detailed message",
    )
    trace: Optional[Sequence[str]] = Query(
        None,
        description="optional stack trace of the error "
        "(only when configured with BAPI_SEND_TRACE=true)",
    )


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
