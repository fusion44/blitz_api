#!/bin/bash

# https://github.com/apotdevin/thunderhub

VERSION=v0.13.31

if [ "$1" = "status" ]; then
  sleep 2s
  echo "version='${VERSION}'"
  echo "installed=1"
  echo "localIP='192.168.1.18'"
  echo "toraddress='toraddress'"
  echo "fingerprint='fingerprint'"
  echo "httpPort='1234'"
  echo "httpsPort='2345'"
  echo "httpsForced='0'"
  echo "httpsSelfsigned='1'"
  echo "authMethod='password_b'"
  exit 0
fi

########################################
# ON (activate & config)
########################################

if [ "$1" = "1" ] || [ "$1" = "on" ]; then
  echo "# *** ACTIVATING THUNDERHUB ***"

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

  echo "result='OK'"
  exit 0
fi

########################################
# OFF (deactivate)
########################################

if [ "$1" = "0" ] || [ "$1" = "off" ]; then
  echo "# *** DEACTIVATE THUNDERHUB ***"

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

  echo "# OK, Thunderhub is removed"
  echo "result='OK'"
  exit 0
fi

echo "FAIL - Unknown Parameter $1"
exit 1
