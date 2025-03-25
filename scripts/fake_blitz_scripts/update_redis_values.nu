#!/usr/bin/env nu

def set_redis_value [key:string, value:string] {
  let result = redis-cli set $key $value | complete
  let is_ok = ($result.stdout | str trim) == "OK"

  if ($is_ok == false) {
      print $"Warning: Redis operation failed: {($result.stdout)} ({($result.stderr)})"
  }
}

# set some fake data that are normally dynamic on a real Blitz
set_redis_value "setupPhase" "done"
set_redis_value "tor_web_addr" "the.onion.address"
set_redis_value "internet_online" "1"
set_redis_value "internet_localip" "192.168.1.132"
set_redis_value "internet_localiprange" "192.168.1.0/24"
set_redis_value "state" "ready"
set_redis_value "message" "Node Running"
set_redis_value "btc_default_sync_initial_done" "1"
set_redis_value "hostname" "fake_blitz"
set_redis_value "ln_default_address" "default_ln_address_of_fake_blitz"
set_redis_value "raspiBlitzVersion" "1.11.4-fake-blitz"
set_redis_value "codeVersion" "1.11.4-fake-blitz"

# The "lightning" value is used in the API, so we need to properly set it
let lines = open .env | lines
$lines | each { |line|
  let parts = $line | split row "="
  if ($parts | first | $in =~ "BAPI_LN_NODE") {
    # lnd_grpc, cln_jrpc, cln_grpc, none
    if ($parts | last | str starts-with "none") {
      print "ln node is none"
      set_redis_value "lightning" "none"
    } else if ($parts | last | str starts-with "lnd") {
      print "ln node is lnd"
      set_redis_value "lightning" "lnd"
    } else if ($parts | last | str starts-with "cln") {
      print "ln node is cln"
      set_redis_value "lightning" "cl"
    } else {
      print "BAPI_LN_NODE must be one of lnd_grpc, cln_jrpc, cln_grpc, none"
      print "Unrecoverable error. Exiting."
      exit 1
    }
  }
}

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
