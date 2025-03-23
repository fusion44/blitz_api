#!/bin/bash

VERSION="v3.4.0"


if [ "$1" = "status" ]; then

  sleep 2s
  echo "version='${VERSION}'"
  echo "installed=1"
  echo "configured=1"

  echo "localIP='192.168.1.18'"
  echo "httpPort='3020'"
  echo "httpsPort='3021'"
  echo "httpsForced='0'"
  echo "httpsSelfsigned='1'"
  echo "authMethod='user_admin_password_b'"
  echo "toraddress='btcrpcexplorer123456789onion.onion'"
  echo "fingerprint='AA:BB:CC:DD:EE:FF:11:22:33:44:55:66:77:88:99:00'"

  echo "isIndexed=1"
  echo "indexInfo='Blockchain index is ready.'"
  exit 0
fi

########################################
# UNINSTALL (remove from system)
########################################

if [ "$1" = "uninstall" ]; then

  echo "# *** UNINSTALL BTC-RPC-EXPLORER ***"
  echo "# removing user btcrpcexplorer"
  sleep 2s
  echo "# removing service files"
  sleep 2s
  echo "# uninstall done"

  exit 0
fi

########################################
# ON (activate & config)
########################################

if [ "$1" = "1" ] || [ "$1" = "on" ]; then

  echo "# *** ACTIVATE BTC-RPC-EXPLORER ***"
  echo "# getting RPC credentials"
  sleep 2s

  echo "# creating environment configuration"
  sleep 2s

  echo "# updating firewall"
  echo "# opening ports 3020 and 3021"
  sleep 1s

  echo "# setting up NGINX"
  sleep 3s

  echo "# installing systemd service"
  sleep 2s

  echo "# enabling service"
  sleep 1s

  echo "# configuring Tor Hidden Service"
  sleep 2s

  echo "# starting service"
  sleep 5s

  echo "# OK - the BTC-RPC-explorer service is now enabled"
  echo "result='OK'"
  exit 0
fi

########################################
# OFF (deactivate)
########################################

if [ "$1" = "0" ] || [ "$1" = "off" ]; then

  echo "# *** REMOVING BTC-RPC-explorer ***"
  echo "# stopping service"
  sleep 2s

  echo "# disabling systemd service"
  sleep 1s

  echo "# removing service files"
  sleep 2s

  echo "# removing NGINX configurations"
  sleep 2s

  echo "# removing Tor Hidden Service"
  sleep 1s

  echo "# closing firewall ports"
  sleep 1s

  echo "# OK BTC-RPC-explorer removed."
  echo "result='OK'"
  exit 0
fi

echo "error='unknown parameter'"
exit 1
