import time
import logging

HW_INFO_YIELD_TIME = 2


from fastapi_plugins import redis_plugin as r


async def _redis_get(key: str) -> str:
    v = await r.redis.get(key)

    if not v:
        logging.warning(f"Key '{key}' not found in Redis DB.")
        return ""

    return v.decode("utf-8")


async def get_hardware_info_impl() -> map:
    info = {}

    loads = (await _redis_get("system_cpu_load")).split(",")
    iloads = []
    total = 0
    for l in loads:
        value = float(l)
        total += value
        iloads.append(value)
    info["cpu_overall_percent"] = total / len(loads)
    info["cpu_per_cpu_percent"] = iloads

    info["vram_total_bytes"] = int(await _redis_get("system_ram_mb")) * 1000 * 1000

    info["vram_available_bytes"] = (
        int(await _redis_get("system_ram_available_mb")) * 1000 * 1000
    )

    info["vram_used_bytes"] = info["vram_total_bytes"] - info["vram_available_bytes"]
    info["vram_usage_percent"] = (100 / info["vram_total_bytes"]) * info[
        "vram_used_bytes"
    ]

    info["temperatures_celsius"] = {
        "system_temp": float(await _redis_get("system_temp_celsius")),
        "coretemp": [],
    }

    now = time.time()
    boot = float(await _redis_get("system_up"))
    info["boot_time_timestamp"] = now - boot

    total = int(await _redis_get("hdd_capacity_bytes"))
    free = int(await _redis_get("hdd_free_bytes"))
    info["disks"] = [
        {
            "device": "/",
            "mountpoint": "/",
            "filesystem_type": "ext4",
            "partition_total_bytes": total,
            "partition_used_bytes": total - free,
            "partition_free_bytes": free,
            "partition_percent": (100 / total) * free,
        }
    ]

    info["networks"] = {
        "public_ip": await _redis_get("publicIP"),
        "internet_online": await _redis_get("internet_online"),
        "tor_web_addr": await _redis_get("tor_web_addr"),
        "internet_localip=": await _redis_get("internet_localip"),
        "internet_localiprange": await _redis_get("internet_localiprange"),
    }

    return info
