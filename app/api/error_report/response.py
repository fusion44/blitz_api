from typing import Optional, Sequence

from starlette.responses import JSONResponse

from app.api.config import config
from app.api.models import ErrorMessage


def _flag(name: str) -> bool:
    return bool(config(name, default=False, cast=bool))


def build_error_response(
    status_code: int,
    detail: str,
    error_code: str = "",
    report=None,
    trace: Optional[Sequence[str]] = None,
    report_sensitive: bool = True,
) -> JSONResponse:
    """Build the canonical ErrorMessage JSONResponse.

    `report` is included only when it is non-sensitive or `BAPI_SEND_REPORT` is
    set; `trace` only when `BAPI_SEND_TRACE` is set.
    """
    include_report = report is not None and (
        not report_sensitive or _flag("BAPI_SEND_REPORT")
    )
    include_trace = trace is not None and _flag("BAPI_SEND_TRACE")

    message = ErrorMessage(
        detail=str(detail),
        error_code=error_code or "",
        report=report if include_report else None,
        trace=list(trace) if include_trace else None,
    )
    return JSONResponse(status_code=status_code, content=message.model_dump())
