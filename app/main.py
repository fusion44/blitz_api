import asyncio
import sys
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import HTTPException, RequestValidationError
from loguru import logger
from pydantic import BaseModel
from redis.asyncio import Redis
from starlette import status
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import RedirectResponse
from starlette.websockets import WebSocketDisconnect

from app.api.config import config as dconfig
from app.api.error_report.report import Report
from app.api.error_report.response import build_error_response
from app.api.models import ApiErrors, StartupState
from app.api.startup_status import api_startup_status
from app.api.utils import Event, broadcast_msg
from app.api.warmup import (
    get_bitcoin_client_warmup_data,
    get_full_client_warmup_data,
    get_full_client_warmup_data_bitcoinonly,
)
from app.api.ws_manager import ws_mgr
from app.apps.router import register_app_status_update_handlers
from app.apps.router import router as app_router
from app.auth.auth_handler import (
    handle_local_cookie,
    register_cookie_updater,
    remove_local_cookie,
)
from app.bitcoind.router import router as bitcoin_router
from app.bitcoind.service import (
    initialize_bitcoin_repo,
    register_bitcoin_status_gatherer,
    register_bitcoin_zmq_sub,
)
from app.external.fastapi_plugins_redis import (
    RedisSettings,
    get_config as get_redis_config,
    redis_plugin,
    registered_configuration,
)
from app.external.result_type.src.result.result import Ok
from app.lightning.models import LnInitState
from app.lightning.router import router as ln_router
from app.lightning.service import initialize_ln_repo, register_lightning_listener
from app.logging import configure_logger
from app.setup.router import router as setup_router
from app.system.router import router as system_router
from app.system.service import get_hardware_info, register_hardware_info_gatherer

configure_logger()


remote_debugging = dconfig("BAPI_REMOTE_DEBUGGING", cast=bool, default=False)
if remote_debugging:
    logger.warning(
        (
            "Remote debugging is enabled, this can be a security issue. "
            "Only enable on development machines."
        )
    )
    remote_debugging_port = dconfig(
        "BAPI_REMOTE_DEBUGGING_PORT", cast=int, default=5678
    )

    try:
        import debugpy
    except ImportError:
        logger.error("Remote debugging is enabled, but debugpy is not installed.")
        sys.exit(1)

    debugpy.listen(("0.0.0.0", remote_debugging_port))

node_type = dconfig("BAPI_LN_NODE", default="none").lower()
if node_type == "":
    node_type = "none"


@registered_configuration
class AppSettings(RedisSettings):
    api_name: str = str(__name__)


config = get_redis_config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # setup
    await redis_plugin.init_app(app, config=config)
    await redis_plugin.init()
    redis = redis_plugin.redis
    if not isinstance(redis, Redis):
        raise RuntimeError("Redis not initialized correctly, got a Sentinel")

    register_cookie_updater()
    await broadcast_msg(Event.SYSTEM_STARTUP_INFO, api_startup_status.model_dump())
    btc_task = asyncio.create_task(_initialize_bitcoin())
    ln_task = asyncio.create_task(_initialize_lightning())
    await register_all_handlers()
    handle_local_cookie()

    yield

    # cleanup
    await redis_plugin.terminate()
    await btc_task
    await ln_task
    remove_local_cookie()


app = FastAPI(lifespan=lifespan)
app.include_router(app_router)
app.include_router(bitcoin_router)
if node_type != "none":
    app.include_router(ln_router)
app.include_router(system_router)
if setup_router is not None:
    app.include_router(setup_router)

origins = [
    "http://localhost",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(StarletteHTTPException)
@app.exception_handler(HTTPException)
async def http_e_handler(_: Request, e: HTTPException):
    # Normalize every HTTPException into the ErrorMessage shape.
    detail = e.detail
    if isinstance(detail, dict) and "detail" in detail:
        # already an ErrorMessage-shaped dict (e.g. the apps code)
        return build_error_response(
            e.status_code,
            detail=str(detail.get("detail", "")),
            error_code=str(detail.get("error_code", "") or ""),
            report=detail.get("report"),
            trace=detail.get("trace"),
            report_sensitive=True,
        )
    return build_error_response(e.status_code, detail=str(detail))


@app.exception_handler(RequestValidationError)
async def valid_e_handler(_: Request, exc: RequestValidationError):
    errors = exc.errors()
    try:
        return build_error_response(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=errors[0]["msg"],
            error_code=ApiErrors.INVALID_REQUEST_INPUT,
            report=errors,
            report_sensitive=False,  # field-error array is non-sensitive
        )
    except Exception as e:
        tb = traceback.format_exception(e)
        logger.error(f"error processing RequestValidationError: {e}\n{tb}")
        report = Report("error while processing RequestValidationError", e).attach(exc)
        return build_error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="error processing RequestValidationError",
            error_code=ApiErrors.UNABLE_TO_PROCESS_ERROR,
            report=report.format_verbose(),
            trace=tb,
        )


@app.exception_handler(Exception)
async def unhandled_e_handler(_: Request, exc: Exception):
    tb = traceback.format_exception(exc)
    logger.error(f"unhandled exception: {exc}\n{''.join(tb)}")
    report = Report("unhandled exception", exc)
    return build_error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Internal server error",
        error_code=ApiErrors.UNKNOWN,
        report=report.format_verbose(),
        trace=tb,
    )


async def _set_startup_status(
    bitcoin: None | StartupState = None,
    bitcoin_msg: None | str = None,
    lightning: None | StartupState = None,
    lightning_msg: None | str = None,
):
    # We must know when both bitcoin and lightning are initialized
    # to trigger the warmup method for new SSE clients
    if bitcoin is not None:
        api_startup_status.bitcoin = bitcoin
    if bitcoin_msg is not None:
        api_startup_status.bitcoin_msg = bitcoin_msg
    if lightning is not None:
        api_startup_status.lightning = lightning
    if lightning_msg is not None:
        api_startup_status.lightning_msg = lightning_msg

    asyncio.create_task(warmup_new_connections())
    await broadcast_msg(Event.SYSTEM_STARTUP_INFO, api_startup_status.model_dump())


@logger.catch
async def _initialize_bitcoin():
    await _set_startup_status(bitcoin=StartupState.OFFLINE)
    await initialize_bitcoin_repo()
    await register_bitcoin_zmq_sub()
    await register_bitcoin_status_gatherer()
    await _set_startup_status(bitcoin=StartupState.DONE)


@logger.catch
async def _initialize_lightning():
    if node_type == "none":
        api_startup_status.lightning = StartupState.DISABLED
        api_startup_status.lightning_msg = ""
        await _set_startup_status(lightning=StartupState.DISABLED)
        logger.info("Lightning node is disabled, skipping initialization")
        return

    try:
        async for u in initialize_ln_repo():
            ln_status = None
            ln_msg = None
            changed = False
            if (
                u.state == LnInitState.OFFLINE
                and api_startup_status.lightning != StartupState.OFFLINE
            ):
                ln_status = StartupState.OFFLINE
                changed = True
            elif (
                u.state == LnInitState.BOOTSTRAPPING
                and api_startup_status.lightning != StartupState.BOOTSTRAPPING
            ):
                ln_status = StartupState.BOOTSTRAPPING
                changed = True
            elif (
                u.state == LnInitState.LOCKED
                and api_startup_status.lightning != StartupState.LOCKED
            ):
                ln_status = StartupState.LOCKED
                changed = True
            elif (
                u.state == LnInitState.BOOTSTRAPPING_AFTER_UNLOCK
                and api_startup_status != LnInitState.BOOTSTRAPPING_AFTER_UNLOCK
            ):
                ln_status = LnInitState.BOOTSTRAPPING_AFTER_UNLOCK
                changed = True
            elif (
                u.state == LnInitState.DONE
                and api_startup_status.lightning != StartupState.DONE
            ):
                # We've successfully connected to the lightning node
                # We can now register all lightning listeners
                await register_lightning_listener()
                ln_status = StartupState.DONE
                ln_msg = ""
                changed = True

            if api_startup_status.lightning_msg != u.msg:
                ln_msg = u.msg
                changed = True

            if changed:
                await _set_startup_status(lightning=ln_status, lightning_msg=ln_msg)

    except HTTPException as r:
        logger.error(r.detail)
    except NotImplementedError as r:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail=r.args[0])


@app.get("/")
def index(req: Request):
    logger.info(req.url)
    p = req.scope.get("root_path")
    return RedirectResponse(
        f"{p}/docs",
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )


new_connections = []


async def _send_ws_event(id, event, data):
    return await ws_mgr.send_to_single(id, event, data)


@app.websocket("/ws")
async def stream(websocket: WebSocket):
    conn_id, authed = await ws_mgr.connect(websocket)
    if not authed:
        return  # ws_mgr already closed the socket

    new_connections.append(conn_id)
    await _send_ws_event(
        conn_id,
        Event.SYSTEM_STARTUP_INFO,
        jsonable_encoder(api_startup_status.model_dump()),
    )
    asyncio.create_task(warmup_new_connections())

    try:
        while True:
            # server-push only; receive loop just detects disconnect
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_mgr.disconnect(conn_id)
        if conn_id in new_connections:
            new_connections.remove(conn_id)


warmup_running = False


async def warmup_new_connections():
    # This doesn't keep track of which connection has received
    # which data already, so it may send data twice data to the client
    # when the startup state changes. Especially the hardware info
    # is rather data intensive. This is OK for now, to keep the code simple.

    async def _handle(id, event, res):
        match res:
            case BaseModel():
                return await _send_ws_event(id, event, res.model_dump())
            case dict() | list():
                return await _send_ws_event(id, event, res)
            case Ok(data) if data and isinstance(data, BaseModel):
                return await _send_ws_event(id, event, data.model_dump())
            case Ok(data) if not data:
                logger.debug(f"No data to send for warmup event {event}")
                return
            case data:
                logger.warning(
                    f"Got unknown data type while handling warmup "
                    f"data {event}: {type(res)}"
                )

        logger.error(f"Error while fetching warmup_data for {event}: {res}")
        return await _send_ws_event(id, event, {"error": f"{res}"})

    global new_connections
    if len(new_connections) == 0:
        return

    global warmup_running
    if warmup_running:
        logger.debug("Warmup already running, skipping")
        return

    warmup_running = True
    try:
        is_ready = api_startup_status.is_fully_initialized()

        if is_ready:
            # when lightning is active
            if node_type != "" and node_type != "none":
                res = await get_full_client_warmup_data()
                for id in new_connections:
                    await asyncio.gather(
                        *[
                            _handle(id, Event.SYSTEM_INFO, res[0]),
                            _handle(id, Event.BTC_INFO, res[1]),
                            _handle(id, Event.LN_INFO, res[2]),
                            _handle(id, Event.LN_FEE_REVENUE, res[3]),
                            _handle(id, Event.WALLET_BALANCE, res[4]),
                            _handle(id, Event.APP_STATE_MESSAGE, res[5]),
                            _handle(id, Event.HARDWARE_INFO, res[6]),
                        ]
                    )

            # when its bitcoin only
            else:
                res = await get_full_client_warmup_data_bitcoinonly()
                for id in new_connections:
                    await asyncio.gather(
                        *[
                            _handle(id, Event.SYSTEM_INFO, res[0]),
                            _handle(id, Event.BTC_INFO, res[1]),
                            _handle(id, Event.APP_STATE_MESSAGE, res[2]),
                            _handle(id, Event.HARDWARE_INFO, res[3]),
                        ]
                    )

            new_connections.clear()
            return

        if (
            api_startup_status.bitcoin == StartupState.DONE
            and api_startup_status.lightning != StartupState.DONE
        ):
            res = await get_bitcoin_client_warmup_data()
            for id in new_connections:
                await asyncio.gather(
                    *[
                        _handle(id, Event.BTC_INFO, res[0]),
                        _handle(id, Event.HARDWARE_INFO, res[1]),
                    ]
                )

            # don't clear new_connections,
            # we'll try again later when api is initialized

        if (
            api_startup_status.bitcoin != StartupState.DONE
            and api_startup_status.lightning != StartupState.DONE
        ):
            # send only the most minimal available data without
            # Bitcoin Core and Lightning running
            res = await get_hardware_info()
            for id in new_connections:
                await _send_ws_event(id, Event.HARDWARE_INFO, res)

            # don't clear new_connections,
            # we'll try again later when api is initialized

    except Exception as e:
        # never let an error escape: this runs as a fire-and-forget task and
        # a stuck warmup_running flag would starve all future SSE clients
        logger.exception(f"Error during warmup of new SSE connections: {e}")
    finally:
        warmup_running = False


register_handlers_finished = False


async def register_all_handlers():
    global register_handlers_finished

    if register_handlers_finished:
        raise RuntimeError("register_all_handlers() must not be called twice.")

    await register_app_status_update_handlers()
    await register_hardware_info_gatherer()

    register_handlers_finished = True
