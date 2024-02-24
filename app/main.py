import asyncio
import sys
from contextlib import asynccontextmanager

from decouple import config as dconfig
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import HTTPException
from fastapi_plugins import (
    RedisSettings,
    get_config,
    redis_plugin,
    registered_configuration,
)
from loguru import logger
from starlette import status
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import RedirectResponse

from app.api.models import ApiStartupStatus, StartupState
from app.api.utils import SSE, broadcast_sse_msg, build_sse_event, sse_mgr
from app.api.warmup import (
    get_bitcoin_client_warmup_data,
    get_full_client_warmup_data,
    get_full_client_warmup_data_bitcoinonly,
)
from app.apps.router import router as app_router
from app.auth.auth_bearer import JWTBearer
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
from app.lightning.models import LnInitState
from app.lightning.router import router as ln_router
from app.lightning.service import initialize_ln_repo, register_lightning_listener
from app.logging import configure_logger
from app.setup.router import router as setup_router
from app.system.router import router as system_router
from app.system.service import get_hardware_info, register_hardware_info_gatherer

configure_logger()


remote_debugging = dconfig("remote_debugging", cast=bool, default=False)
if remote_debugging:
    logger.warning(
        (
            "Remote debugging is enabled, this can be a security issue. "
            "Only enable on development machines."
        )
    )
    remote_debugging_port = dconfig("remote_debugging_port", cast=int, default=5678)

    try:
        import debugpy
    except ImportError:
        logger.error("Remote debugging is enabled, but debugpy is not installed.")
        sys.exit(1)

    debugpy.listen(("0.0.0.0", remote_debugging_port))

node_type = dconfig("ln_node").lower()
if node_type == "":
    node_type = "none"


@registered_configuration
class AppSettings(RedisSettings):
    api_name: str = str(__name__)


config = get_config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # setup
    await redis_plugin.init_app(app, config=config)
    await redis_plugin.init()
    register_cookie_updater()
    await broadcast_sse_msg(SSE.SYSTEM_STARTUP_INFO, api_startup_status.model_dump())
    loop = asyncio.get_event_loop()
    loop.create_task(_initialize_bitcoin())
    loop.create_task(_initialize_lightning())
    await register_all_handlers()
    handle_local_cookie()

    yield

    # cleanup
    await redis_plugin.terminate()
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


api_startup_status = ApiStartupStatus()


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

    loop = asyncio.get_event_loop()
    loop.create_task(warmup_new_connections())
    await broadcast_sse_msg(SSE.SYSTEM_STARTUP_INFO, api_startup_status.model_dump())


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

    return RedirectResponse(
        "/api/docs",
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )


new_connections = []


def _send_sse_event(id, event, data):
    return sse_mgr.send_to_single(id, build_sse_event(event, data))


@app.get(
    "/sse/subscribe",
    status_code=status.HTTP_200_OK,
)
async def stream(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        # No token in cookies found, try to get it from the Authorization header
        token = request.headers.get("authorization")

    if not token:
        # Raise an exception as there is not token found
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No authorization code.",
        )

    token = token.replace("Bearer ", "")
    if not JWTBearer().verify_jwt(jwtoken=token):
        # token is invalid
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization code.",
        )

    event_source, id = sse_mgr.add_connection(request)
    new_connections.append(id)

    await _send_sse_event(
        id, SSE.SYSTEM_STARTUP_INFO, jsonable_encoder(api_startup_status.model_dump())
    )

    loop = asyncio.get_event_loop()
    loop.create_task(warmup_new_connections())

    return event_source


warmup_running = False


async def warmup_new_connections():
    # This doesn't keep track of which connection has received
    # which data already, so it may send data twice data to the client
    # when the startup state changes. Especially the hardware info
    # is rather data intensive. This is OK for now, to keep the code simple.

    global new_connections
    if len(new_connections) == 0:
        return

    global warmup_running
    if warmup_running:
        logger.debug("Warmup already running, skipping")
        return

    warmup_running = True
    is_ready = api_startup_status.is_fully_initialized()

    if is_ready:
        # when lightning is active
        if node_type != "" and node_type != "none":
            res = await get_full_client_warmup_data()
            for id in new_connections:
                await asyncio.gather(
                    *[
                        _send_sse_event(id, SSE.SYSTEM_INFO, res[0].dict()),
                        _send_sse_event(id, SSE.BTC_INFO, res[1].dict()),
                        _send_sse_event(id, SSE.LN_INFO, res[2].dict()),
                        _send_sse_event(id, SSE.LN_INFO_LITE, res[3].dict()),
                        _send_sse_event(id, SSE.LN_FEE_REVENUE, res[4]),
                        _send_sse_event(id, SSE.WALLET_BALANCE, res[5].dict()),
                        _send_sse_event(id, SSE.INSTALLED_APP_STATUS, res[6]),
                        _send_sse_event(id, SSE.HARDWARE_INFO, res[7]),
                    ]
                )

        # when its bitcoin only
        else:
            res = await get_full_client_warmup_data_bitcoinonly()
            for id in new_connections:
                await asyncio.gather(
                    *[
                        _send_sse_event(id, SSE.SYSTEM_INFO, res[0].dict()),
                        _send_sse_event(id, SSE.BTC_INFO, res[1].dict()),
                        _send_sse_event(id, SSE.HARDWARE_INFO, res[2]),
                    ]
                )

        new_connections.clear()

    if (
        api_startup_status.bitcoin == StartupState.DONE
        and api_startup_status.lightning != StartupState.DONE
    ):
        res = await get_bitcoin_client_warmup_data()
        for id in new_connections:
            await asyncio.gather(
                *[
                    _send_sse_event(id, SSE.BTC_INFO, res[0].dict()),
                    _send_sse_event(id, SSE.HARDWARE_INFO, res[1]),
                ]
            )

        # don't clear new_connections, we'll try again later when api is initialized

    if (
        api_startup_status.bitcoin != StartupState.DONE
        and api_startup_status.lightning != StartupState.DONE
    ):
        # send only the most minimal available data without
        # Bitcoin Core and Lightning running
        res = await get_hardware_info()
        for id in new_connections:
            await _send_sse_event(id, SSE.HARDWARE_INFO, res),

        # don't clear new_connections, we'll try again later when api is initialized

    warmup_running = False


register_handlers_finished = False


async def register_all_handlers():
    global register_handlers_finished

    if register_handlers_finished:
        raise RuntimeError("register_all_handlers() must not be called twice.")

    await register_hardware_info_gatherer()

    register_handlers_finished = True
