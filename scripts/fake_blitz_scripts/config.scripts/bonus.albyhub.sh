#!/bin/bash

# https://github.com/getAlby/hub

VERSION=1.15.0

if [ "$1" = "status" ]; then
  sleep 2s
  echo "appID='albyhub'"
  echo "version='${VERSION}'"
  echo "installed=0"
  echo "localIP='192.168.1.18'"
  echo "toraddress='toraddress'"
  echo "fingerprint='fingerprint'"
  echo "httpPort='1234'"
  echo "httpsPort='2345'"
  echo "httpsForced='1'"
  echo "httpsSelfsigned='1'"
  echo "authMethod='userdefined'"
  exit 0
fi

########################################
# ON (activate & config)
########################################

if [ "$1" = "1" ] || [ "$1" = "on" ]; then
  echo "# *** ACTIVATING ALBYHUB ***"

  echo "# Setting up NGINX configuration"
  sleep 3s

  echo "# Updating firewall rules"
  sleep 1s

  echo "# Generating SSL certificates"
  sleep 2s

  echo "# Installing systemd service"
  sleep 2s

  echo "# Setting up Tor Hidden Service"
  sleep 2s

  echo "# Starting services"
  sleep 3s

  echo "# Starting order book service"
  sleep 2s

  echo "# For the connection details run: /home/admin/config.scripts/bonus.albyhub.sh menu"
  echo "result='OK'"
  exit 0
fi

########################################
# OFF (deactivate)
########################################

if [ "$1" = "0" ] || [ "$1" = "off" ]; then
  echo "# *** DEACTIVATE ALBYHUB ***"

  echo "# Stopping services"
  sleep 2s

  echo "# Disabling systemd service"
  sleep 1s

  echo "# Removing service files"
  sleep 1s

  echo "# Closing firewall ports"
  sleep 1s

  echo "# Removing NGINX configurations"
  sleep 2s

  echo "# Removing Tor Hidden Service"
  sleep 2s

  echo "# Removing SSL certificates"
  sleep 1s

  echo "# OK, Albyhub is removed"
  echo "result='OK'"
  exit 0
fi

echo "FAIL - Unknown Parameter $1"
exit 1
