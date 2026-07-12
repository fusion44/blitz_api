from app.api.models import ApiStartupStatus, StartupState
from app.system.health import build_health_info


def _names(info):
    return [s.name for s in info.subsystems]


def _by_name(info, name):
    return next(s for s in info.subsystems if s.name == name)


def test_all_ready_is_healthy_no_subsystems_without_verbose():
    status = ApiStartupStatus(
        bitcoin=StartupState.DONE, lightning=StartupState.DONE
    )
    info = build_health_info(status, verbose=False)
    assert info.healthy is True
    assert info.message == ""
    assert info.subsystems == []


def test_verbose_lists_three_subsystems_in_order():
    status = ApiStartupStatus(
        bitcoin=StartupState.DONE, lightning=StartupState.DONE
    )
    info = build_health_info(status, verbose=True)
    assert _names(info) == ["api", "bitcoind", "lightning"]
    assert _by_name(info, "api").healthy is True
    assert _by_name(info, "bitcoind").healthy is True
    assert _by_name(info, "lightning").healthy is True


def test_bitcoin_bootstrapping_is_unhealthy():
    status = ApiStartupStatus(
        bitcoin=StartupState.BOOTSTRAPPING, lightning=StartupState.DONE
    )
    info = build_health_info(status, verbose=True)
    assert info.healthy is False
    assert info.message == "bitcoind not ready: bootstrapping"
    assert _by_name(info, "bitcoind").healthy is False
    assert _by_name(info, "bitcoind").message == "bootstrapping"


def test_bitcoin_message_is_appended_when_present():
    status = ApiStartupStatus(
        bitcoin=StartupState.BOOTSTRAPPING,
        bitcoin_msg="syncing headers",
        lightning=StartupState.DONE,
    )
    info = build_health_info(status, verbose=True)
    assert _by_name(info, "bitcoind").message == "bootstrapping: syncing headers"


def test_lightning_disabled_is_healthy_on_bitcoin_only_node():
    status = ApiStartupStatus(
        bitcoin=StartupState.DONE, lightning=StartupState.DISABLED
    )
    info = build_health_info(status, verbose=True)
    assert info.healthy is True
    ln = _by_name(info, "lightning")
    assert ln.healthy is True
    assert ln.message == "disabled"


def test_lightning_locked_is_unhealthy():
    status = ApiStartupStatus(
        bitcoin=StartupState.DONE, lightning=StartupState.LOCKED
    )
    info = build_health_info(status, verbose=True)
    assert info.healthy is False
    assert info.message == "lightning not ready: locked"
    assert _by_name(info, "lightning").healthy is False
