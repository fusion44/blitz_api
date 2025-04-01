#!/bin/bash

# https://github.com/lnbits/lnbits/releases
tag="v0.12.11"
VERSION="${tag}"


if [ "$1" = "status" ]; then
  sleep 2s
  echo "version='${VERSION}'"
  echo "installed=0"
  echo "localIP='192.168.1.18'"
  echo "httpPort='5000'"
  echo "httpsPort='5001'"
  echo "httpsForced='1'"
  echo "httpsSelfsigned='1'"
  echo "publicIP='47.128.65.12'"
  echo "authMethod='/wallet?usr=admin123456789abcdef'"
  echo "LNBitsFunding='lnd'"
  echo "publicDomain='lnbits.example.com'"
  echo "sslFingerprintIP='AA:BB:CC:DD:EE:FF:11:22:33:44:55:66:77:88:99:00'"
  echo "toraddress='lnbits7xbr5zuuhdeemrtqcpz.onion'"
  echo "sslFingerprintTOR='BB:CC:DD:EE:FF:11:22:33:44:55:66:77:88:99:00:AA'"
  exit 0
fi

########################################
# ON (activate & config)
########################################

if [ "$1" = "1" ] || [ "$1" = "on" ]; then
  # get funding source
  fundingsource="$2"

  if [ "${fundingsource}" == "" ]; then
    echo "# Running with default lightning as funding source: lnd"
    fundingsource="lnd"
  fi

  echo "# ACTIVATING LNBITS with funding source: ${fundingsource}"

  echo "# Preparing data directory"
  sleep 1s

  echo "# Setting up environment configuration"
  sleep 2s

  echo "# Configuring database"
  sleep 3s

  echo "# Updating firewall rules"
  sleep 1s

  echo "# Installing systemd service"
  sleep 2s

  echo "# Setting up NGINX"
  sleep 2s

  echo "# Configuring Tor Hidden Service"
  sleep 2s

  echo "# Starting service"
  sleep 3s

  echo "# OK install done"
  echo "result='OK'"
  exit 0
fi

########################################
# OFF (deactivate)
########################################

if [ "$1" = "0" ] || [ "$1" = "off" ]; then
  deleteData=0
  if [ "$2" = "--delete-data" ]; then
    deleteData=1
    echo "# Will delete data during uninstall"
  elif [ "$2" = "--keep-data" ]; then
    deleteData=0
    echo "# Will keep data during uninstall"
  fi

  echo "# *** REMOVING LNBITS ***"

  echo "# Stopping service"
  sleep 2s

  echo "# Disabling service"
  sleep 1s

  echo "# Removing service file"
  sleep 1s

  echo "# Closing firewall ports"
  sleep 1s

  echo "# Removing NGINX configurations"
  sleep 2s

  echo "# Removing Tor Hidden Service"
  sleep 2s

  if [ ${deleteData} -eq 1 ]; then
    echo "# Deleting data"
    sleep 3s
  else
    echo "# Keeping data"
  fi

  echo "result='OK'"
  exit 0
fi

echo "FAIL - Unknown Parameter $1"
exit 1
