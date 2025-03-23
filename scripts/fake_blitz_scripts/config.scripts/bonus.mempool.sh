#!/bin/bash

# https://github.com/mempool/mempool

pinnedVersion="v3.0.0"

if [ "$1" = "status" ]; then
  sleep 1s
  echo "version='${pinnedVersion}'"
  echo "codebase=1"
  echo "configured=1"
  echo "installed=1"
  echo "localIP='192.168.1.18'"
  echo "httpPort='4080'"
  echo "httpsPort='4081'"
  echo "httpsForced='0'"
  echo "httpsSelfsigned='1'"
  echo "authMethod='none'"
  echo "fingerprint='AA:BB:CC:DD:EE:FF:11:22:33:44:55:66:77:88:99:00'"
  echo "toraddress='mempool4567xcvbdfgqwertyui.onion'"
  echo "isIndexed=1"
  echo "indexInfo='Blockchain index is ready.'"
  exit 0
fi

########################################
# ON (activate & config)
########################################

if [ "$1" = "1" ] || [ "$1" = "on" ]; then
  echo "# *** ACTIVATE MEMPOOL ***"

  echo "# Starting MariaDB"
  sleep 2s

  echo "# Making sure txindex is enabled"
  sleep 1s

  echo "# Creating database"
  sleep 3s

  echo "# Configuring mempool"
  sleep 2s

  echo "# Creating storage directories"
  sleep 1s

  echo "# Setting up web directory"
  sleep 2s

  echo "# Updating firewall rules"
  sleep 1s

  echo "# Setting up NGINX"
  sleep 3s

  echo "# Installing systemd service"
  sleep 2s

  echo "# Starting mempool service"
  sleep 5s

  echo "# Setting up Tor Hidden Service"
  sleep 2s

  echo "# OK - the mempool service is now enabled"
  echo "# needs to finish creating txindex to be functional"
  echo "result='OK'"
  exit 0
fi

########################################
# OFF (deactivate)
########################################

if [ "$1" = "0" ] || [ "$1" = "off" ]; then
  echo "# *** REMOVING Mempool ***"

  echo "# Removing NGINX configurations"
  sleep 2s

  echo "# Removing web directory"
  sleep 1s

  echo "# Removing Tor Hidden Service"
  sleep 2s

  echo "# Closing firewall ports"
  sleep 1s

  echo "# Stopping service"
  sleep 2s

  echo "# Disabling service"
  sleep 1s

  echo "# Removing service file"
  sleep 1s

  echo "# OK Mempool removed."

  echo "result='OK'"
  exit 0
fi

echo "error='unknown parameter'"
exit 1
