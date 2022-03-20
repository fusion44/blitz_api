import psutil
from decouple import config

SLEEP_TIME = config("gather_hw_info_interval", default=2, cast=float)
CPU_AVG_PERIOD = config("cpu_usage_averaging_period", default=0.5, cast=float)
HW_INFO_YIELD_TIME = SLEEP_TIME + CPU_AVG_PERIOD


async def get_hardware_info_impl() -> map:
    info = {}

    info["cpu_overall_percent"] = psutil.cpu_percent(interval=CPU_AVG_PERIOD)
    info["cpu_per_cpu_percent"] = psutil.cpu_percent(
        interval=CPU_AVG_PERIOD, percpu=True
    )

    v = psutil.virtual_memory()
    info["vram_total_bytes"] = v.total
    info["vram_available_bytes"] = v.available
    info["vram_used_bytes"] = v.used
    info["vram_usage_percent"] = v.percent

    s = psutil.swap_memory()
    info["swap_ram_total_bytes"] = s.total
    info["swap_used_bytes"] = s.used
    info["swap_usage_bytes"] = s.percent

    info["temperatures_celsius"] = psutil.sensors_temperatures()
    info["boot_time_timestamp"] = psutil.boot_time()

    disk_io = psutil.disk_io_counters()
    info["disk_io_read_count"] = disk_io.read_count
    info["disk_io_write_count"] = disk_io.write_count
    info["disk_io_read_bytes"] = disk_io.read_bytes
    info["disk_io_write_bytes"] = disk_io.write_bytes

    disks = []
    partitions = psutil.disk_partitions()
    for partition in partitions:
        p = {}
        p["device"] = partition.device
        p["mountpoint"] = partition.mountpoint
        p["filesystem_type"] = partition.fstype

        try:
            usage = psutil.disk_usage(partition.mountpoint)
            p["partition_total_bytes"] = usage.total
            p["partition_used_bytes"] = usage.used
            p["partition_free_bytes"] = usage.free
            p["partition_percent"] = usage.percent
        except PermissionError:
            continue
        disks.append(p)
    info["disks"] = disks

    nets = []
    addresses = psutil.net_if_addrs()
    for name, address in addresses.items():
        net = {}
        nets.append(net)
        net["interface_name"] = name
        for a in address:
            if str(a.family) == "AddressFamily.AF_INET":
                net["address"] = a.address
            elif str(a.family) == "AddressFamily.AF_PACKET":
                net["mac_address"] = a.address

    net_io = psutil.net_io_counters()
    info["networks"] = nets
    info["networks_bytes_sent"] = net_io.bytes_sent
    info["networks_bytes_received"] = net_io.bytes_recv

    return info
