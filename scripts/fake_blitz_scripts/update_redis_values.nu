#!/usr/bin/env nu

def set_redis_value [key:string, value:string] {
  let result = redis-cli set $key $value | complete
  let is_ok = ($result.stdout | str trim) == "OK"

  if ($is_ok == false) {
      print $"Warning: Redis operation failed: {($result.stdout)} ({($result.stderr)})"
  }
}

set_redis_value "setupPhase" "done"
set_redis_value "tor_web_addr" "the.onion.address"

# Set network values in Redis
set_redis_value "internet_online" "1"
set_redis_value "internet_localip" "192.168.1.132"
set_redis_value "internet_localiprange" "192.168.1.0/24"

while true {
  # Get system information
  let cpu_load = (open /proc/loadavg | lines | first | split row " " | first 3 | str join  ",")
  let ram_total = (sys mem | get total | format filesize B | str replace " B" "")
  let ram_available = (sys mem | get total | format filesize B | str replace " B" "")
  let system_temp = (sys temp | first | get temp | to text) # just get the first one
  let uptime_seconds = (open /proc/uptime | grep -o '^[0-9]\+')

  # Set values in Redis
  set_redis_value "system_cpu_load" $cpu_load
  set_redis_value "system_ram_mb" $ram_total
  set_redis_value "system_ram_available_mb" $ram_available
  set_redis_value "system_temp_celsius" $system_temp
  set_redis_value "system_up" $uptime_seconds


  # Disk information
  let hdd_capacity_bytes = (sys disks | where mount == "/" | get total | format filesize B | str replace " B" ""| first)
  let hdd_free_bytes = (sys disks | where mount == "/" | get free | format filesize B | str replace " B" "" | first)

  # Set disk values in Redis
  set_redis_value "hdd_capacity_bytes" $hdd_capacity_bytes
  set_redis_value "hdd_free_bytes" $hdd_free_bytes

  print "System information has been updated in Redis."
  sleep 5sec
}
