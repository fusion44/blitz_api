#!/bin/bash

# https://github.com/joinmarket-webui/jam

WEBUI_VERSION=0.3.0
REPO=joinmarket-webui/jam

if [ "$1" = "status" ]; then
  sleep 2s
  echo "version='${WEBUI_VERSION}'"
  echo "installed='0'"
  echo "localIP='192.168.1.18'"
  echo "httpPort='7500'"
  echo "httpsPort='7501'"
  echo "httpsForced='1'"
  echo "httpsSelfsigned='1'"
  echo "authMethod='password_b'"
  echo "toraddress='jamwebui98765dfghjkerty.onion'"
  exit 0
fi

########################################
# ON (activate & config)
########################################

if [ "$1" = "1" ] || [ "$1" = "on" ]; then
  echo "# *** ACTIVATING JAM ***"

  echo "# Setting up NGINX configuration"
  sleep 3s

  echo "# Updating firewall rules"
  sleep 1s

  echo "# Generating SSL certificates"
  sleep 2s

  echo "result='FAKE ERROR FOR TESTING'" >&2
  exit 1

  echo "# Installing systemd service"
  sleep 2s

  echo "# Setting up Tor Hidden Service"
  sleep 2s

  echo "# Starting services"
  sleep 3s

  echo "# Starting order book service"
  sleep 2s

  echo "# For the connection details run: /home/admin/config.scripts/bonus.jam.sh menu"
  echo "result='OK'"
  exit 0
fi

########################################
# OFF (deactivate)
########################################

if [ "$1" = "0" ] || [ "$1" = "off" ]; then
  echo "# *** DEACTIVATE JAM ***"

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

  echo "# OK, Jam is removed"
  echo "result='OK'"
  exit 0
fi

echo "FAIL - Unknown Parameter $1"
exit 1
