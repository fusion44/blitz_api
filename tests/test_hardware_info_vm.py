"""
Regression test for blitz_api#271.

On VM setups (e.g. Proxmox) the RaspiBlitz monitor scripts don't populate
the hardware Redis keys, so system_cpu_load / system_ram_mb / etc. are empty
strings. get_hardware_info did int('')/float('') and raised ValueError,
which killed the _handle_gather_hardware_info background task. It should
return zero values instead of crashing.
"""

from app.system.impl import raspiblitz as rb


async def test_get_hardware_info_tolerates_empty_redis_values(monkeypatch):
    monkeypatch.setattr(
        rb.RaspiBlitzSystem, "_check_shell_scripts_status", lambda self: None
    )
    system = rb.RaspiBlitzSystem()

    async def fake_redis_get(key):
        return ""  # every hardware key empty (VM scenario)

    monkeypatch.setattr(rb, "redis_get", fake_redis_get)

    info = await system.get_hardware_info()  # must not raise

    assert info["cpu_overall_percent"] == 0
    assert info["cpu_per_cpu_percent"] == []
    assert info["vram_total_bytes"] == 0
    assert info["vram_available_bytes"] == 0
    assert info["vram_used_bytes"] == 0
    assert info["vram_usage_percent"] == 0
    assert info["temperatures_celsius"]["system_temp"] == 0
