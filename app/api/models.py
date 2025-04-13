from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Union

from fastapi import Query
from pydantic import BaseModel


class ProcessResult:
    return_code: int | None
    stdout: str
    stderr: str

    def __init__(self, return_code: int | None, stdout: str, stderr: str) -> None:
        self.return_code = return_code
        self.stdout = stdout
        self.stderr = stderr

    def __str__(self) -> str:
        return (
            f"ProcessResult: \nreturn_code: {self.return_code}\n"
            f"stdout: {self.stdout}\n"
            f"stderr: {self.stderr}"
        )


class ApiErrors(str, Enum):
    INVALID_REQUEST_INPUT = "invalid_request_input"
    UNABLE_TO_PROCESS_ERROR = "unable_to_process_error"
    APP_STATUS_UPDATE_FAILED = "app_status_update_failed"
    APP_INVALID_FOR_PLATFORM = "app_invalid_for_platform"
    APP_MANAGE_ON_IS_ALREADY_INSTALLED = "app_manage_on_is_already_installed"
    APP_MANAGE_OFF_IS_NOT_INSTALLED = "app_manage_off_is_not_installed"
    APP_MANAGE_LOCK_HELD = "app_manage_lock_held"
    BACKGROUND_TASK_FAILED = "background_task_failed"
    UNKNOWN = "unknown"


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
