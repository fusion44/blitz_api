def test_main_uses_the_shared_singleton():
    import app.main as main
    from app.api.startup_status import api_startup_status

    # main must read/mutate the exact same object, not its own copy
    assert main.api_startup_status is api_startup_status
