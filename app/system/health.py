from app.api.models import ApiStartupStatus, StartupState
from app.system.models import SubSystemHealthInfo, SystemHealthInfo


def _state_message(state: StartupState, msg: str | None) -> str:
    if msg:
        return f"{state.value}: {msg}"
    return state.value


def _bitcoind_subsystem(status: ApiStartupStatus) -> SubSystemHealthInfo:
    if status.bitcoin == StartupState.DONE:
        return SubSystemHealthInfo(name="bitcoind", healthy=True, message="")
    return SubSystemHealthInfo(
        name="bitcoind",
        healthy=False,
        message=_state_message(status.bitcoin, status.bitcoin_msg),
    )


def _lightning_subsystem(status: ApiStartupStatus) -> SubSystemHealthInfo:
    if status.lightning == StartupState.DISABLED:
        return SubSystemHealthInfo(name="lightning", healthy=True, message="disabled")
    if status.lightning == StartupState.DONE:
        return SubSystemHealthInfo(name="lightning", healthy=True, message="")
    return SubSystemHealthInfo(
        name="lightning",
        healthy=False,
        message=_state_message(status.lightning, status.lightning_msg),
    )


def build_health_info(status: ApiStartupStatus, verbose: bool) -> SystemHealthInfo:
    """Build the SystemHealthInfo from the current startup state.

    Pure and synchronous: healthy == status.is_fully_initialized(). The `api`
    subsystem is always healthy (a response proves the API is alive).
    """
    healthy = status.is_fully_initialized()

    message = ""
    if not healthy:
        if status.bitcoin != StartupState.DONE:
            message = f"bitcoind not ready: {status.bitcoin.value}"
        else:
            message = f"lightning not ready: {status.lightning.value}"

    subsystems: list[SubSystemHealthInfo] = []
    if verbose:
        subsystems = [
            SubSystemHealthInfo(name="api", healthy=True, message=""),
            _bitcoind_subsystem(status),
            _lightning_subsystem(status),
        ]

    return SystemHealthInfo(healthy=healthy, message=message, subsystems=subsystems)
