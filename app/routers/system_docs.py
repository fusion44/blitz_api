get_hw_info_json = """
```JSON
{
  "cpu_overall_percent": 15.8,
  "cpu_per_cpu_percent": [
    11.8,
    6.1,
    12.5,
  ],
  "vram_total_bytes": 25134919680,
  "vram_available_bytes": 17240051712,
  "vram_used_bytes": 6044856320,
  "vram_usage_percent": 31.4,
  "swap_ram_total_bytes": 2147479552,
  "swap_used_bytes": 0,
  "swap_usage_bytes": 0,
  "temperatures_celsius": {
    "coretemp": [
      [
        "Core 1",
        51,
        84,
        100
      ],
      [
        "Core 2",
        53,
        84,
        100
      ],
      [
        "Core 3",
        50,
        84,
        100
      ]
    ]
  },
  "boot_time_timestamp": 1623486468,
  "disk_io_read_count": 254574,
  "disk_io_write_count": 133353,
  "disk_io_read_bytes": 5306839040,
  "disk_io_write_bytes": 5593076736,
  "networks": [
    {
      "interface_name": "lo",
      "address": "127.0.0.1",
      "mac_address": "00:00:00:00:00:00"
    },
    {
      "interface_name": "enp4s0",
      "address": "192.168.1.23",
      "mac_address": "35:a3:5c:6a:4a:f0"
    },
  ],
  "networks_bytes_sent": 137088249,
  "networks_bytes_received": 1603400654
}
```
"""
