import time

from app.utils import redis_get

HW_INFO_YIELD_TIME = 2


from fastapi_plugins import redis_plugin as r


async def get_hardware_info_impl() -> map:
    info = {}

    loads = (await redis_get("system_cpu_load")).split(",")
    iloads = []
    total = 0
    for l in loads:
        value = float(l)
        total += value
        iloads.append(value)
    info["cpu_overall_percent"] = round(total / len(loads), 2)
    info["cpu_per_cpu_percent"] = iloads

    info["vram_total_bytes"] = int(await redis_get("system_ram_mb")) * 1000 * 1000

    info["vram_available_bytes"] = (
        int(await redis_get("system_ram_available_mb")) * 1000 * 1000
    )

    info["vram_used_bytes"] = info["vram_total_bytes"] - info["vram_available_bytes"]
    info["vram_usage_percent"] = round(
        (100 / info["vram_total_bytes"]) * info["vram_used_bytes"], 2
    )

    info["temperatures_celsius"] = {
        "system_temp": float(await redis_get("system_temp_celsius")),
        "coretemp": [],
    }

    now = time.time()
    boot = float(await redis_get("system_up"))
    info["boot_time_timestamp"] = now - boot

    info["networks"] = {
        "internet_online": await redis_get("internet_online"),
        "tor_web_addr": await redis_get("tor_web_addr"),
        "internet_localip": await redis_get("internet_localip"),
        "internet_localiprange": await redis_get("internet_localiprange"),
    }

    # the following is just available when setup is done
    setup_phase = await redis_get("setupPhase")
    info["disks"] = []
    if setup_phase == "done":
        total = int(await redis_get("hdd_capacity_bytes"))
        free = int(await redis_get("hdd_free_bytes"))
        info["disks"] = [
            {
                "device": "/",
                "mountpoint": "/",
                "filesystem_type": "ext4",
                "partition_total_bytes": total,
                "partition_used_bytes": total - free,
                "partition_free_bytes": free,
                "partition_percent": round((100 / total) * free, 2),
            }
        ]

    return info
