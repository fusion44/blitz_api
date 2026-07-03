import asyncio
from typing import List, Optional

from fastapi import HTTPException, status
from loguru import logger

from app.api.error_report.report import Report
from app.api.task_utils import get_lock_status
from app.apps.cache import cache as app_cache
from app.apps.constants import AppManagementProcessState, AppsServiceKeys
from app.apps.models import AppStatusUpdateTaskMessage
from app.apps.tasks import update_app_state_task
from app.bitcoind.service import get_btc_info
from app.external.result_type.src.result.result import Err, Ok, Result
from app.lightning.service import get_fee_revenue, get_ln_info, get_wallet_balance
from app.system.service import get_hardware_info, get_system_info


@logger.catch(exclude=(HTTPException,))
async def get_bitcoin_client_warmup_data() -> List:
    """Get the reduced data set needed when the lightning client is not yet ready."""
    res = await asyncio.gather(
        *[
            get_btc_info(),
            get_hardware_info(),
        ]
    )
    return [*res]


async def _get_app_status_data() -> Result[
    Optional[AppStatusUpdateTaskMessage], Report
]:
    """Transform the result of get_app_status."""
    try:
        result = await app_cache.get_cached_app_status()
        match result:
            case Ok(cached_status_data) if cached_status_data:
                return Ok(
                    AppStatusUpdateTaskMessage(
                        state=AppManagementProcessState.SUCCESS,
                        message=cached_status_data,
                    )
                )
            case Ok(_):
                # Query executed, but no data was returned
                # This means the cache is empty or stale => trigger update
                update_app_state_task.delay()  # type: ignore
                return Ok(None)
            case Err(report):
                # TODO: return error message
                logger.error(f"Failed to fetch app status: {report.format_verbose()}")

        # The cache read failed; check whether an update is already running
        # before triggering a new one
        result = await get_lock_status(AppsServiceKeys.APP_STATUS_LOCK_KEY)
        match result:
            case Ok(True):
                logger.info(
                    "App status update lock exists. Assuming update is in progress."
                )
            case Ok(False):
                logger.info(
                    "App status cache is missing and no update lock exists. "
                    "Triggering update task."
                )
                update_app_state_task.delay()  # type: ignore
            case Err(report):
                return Err(report)

    except Exception as e:
        return Err(
            Report(f"Error during app status cache handling for new client: {e}")
        )

    return Ok(None)


def _convert_warmup_exceptions(res: List) -> List:
    """Convert exceptions from a gather(..., return_exceptions=True) call so
    that a single failing data source doesn't wipe out the whole data set."""
    for i, r in enumerate(res):
        if isinstance(r, HTTPException):
            if r.status_code == status.HTTP_501_NOT_IMPLEMENTED:
                logger.trace(f"Not implemented Error in warmup data {i}: {r.detail}")
            # TODO: find a better way to handle this, client receives an error but
            # disguised as a valid response. For example:
            # event: app_state_update_message
            # data: {
            #   "status_code": 501,
            #   "detail": "Not available in native python mode.",
            #   "headers": null
            # }
            res[i] = r
        elif isinstance(r, Exception):
            logger.error(f"Error in warmup data {i}: {r}")
            res[i] = HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return res


@logger.catch(exclude=(HTTPException,))
async def get_full_client_warmup_data() -> List:
    """Get the full data set needed when the lightning client is not yet ready."""

    res = await asyncio.gather(
        *[
            get_system_info(),
            get_btc_info(),
            get_ln_info(),
            get_fee_revenue(),
            get_wallet_balance(),
            _get_app_status_data(),
            get_hardware_info(),
        ],
        return_exceptions=True,
    )

    return [*_convert_warmup_exceptions(res)]


@logger.catch(exclude=(HTTPException,))
async def get_full_client_warmup_data_bitcoinonly() -> List:
    """Get the full data set needed without Lightning available"""

    res = await asyncio.gather(
        *[
            get_system_info(),
            get_btc_info(),
            _get_app_status_data(),
            get_hardware_info(),
        ],
        return_exceptions=True,
    )
    return [*_convert_warmup_exceptions(res)]
