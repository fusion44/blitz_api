#!/bin/bash

# https://github.com/romanz/electrs/releases
ELECTRSVERSION="v0.10.6"

PGPsigner="romanz"

# give status
if [ "$1" = "status" ]; then

  echo "##### STATUS ELECTRS SERVICE"

  sleep 2s
  echo "version='${ELECTRSVERSION}'"
  echo "configured=1"
  echo "installed=1"

  echo "serviceRunning=1"
  echo "localIP='192.168.1.18'"
  echo "publicIP='47.128.65.12'"
  echo "portTCP='50001'"
  echo "localTCPPortActive=1"
  echo "publicTCPPortAnswering=1"
  echo "portSSL='50002'"
  echo "localHTTPPortActive=1"
  echo "publicHTTPPortAnswering=1"
  echo "TorRunning=1"
  echo "TORaddress='electrssddfgvfert45778.onion'"
  echo "nginxTest=1"

  exit 0
fi

# give sync-status
if [ "$1" = "status-sync" ]; then

  sleep 5s
  echo "serviceRunning=1"
  echo "electrumResponding=1"
  echo "blockheight='790123'"
  echo "blockheightPercent='100'"
  echo "initialSynced=1"

  exit 0
fi

########################################
# ON (activate & config)
########################################

if [ "$1" = "1" ] || [ "$1" = "on" ]; then
  echo "# ACTIVATING ELECTRS"

  echo "# Creating app storage directory"
  sleep 1s

  echo "# Getting RPC credentials from the bitcoin.conf"
  sleep 2s

  echo "# Generating electrs.toml setting file with the RPC passwords"
  sleep 2s

  echo "# Setting up the nginx.conf"
  sleep 3s

  echo "# Open ports 50001 and 50002 on UFW"
  sleep 1s

  echo "# Installing the systemd service"
  sleep 2s

  echo "# Setting Tor Hidden Service"
  sleep 2s

  echo "# Cleaning up build artifacts"
  sleep 1s

  echo "# Starting services"
  sleep 5s

  echo "# ELECTRS is now enabled and running"
  echo "# To connect through SSL from outside of the local network make sure the port 50002 is forwarded on the router"

  exit 0
fi

########################################
# OFF (deactivate)
########################################

if [ "$1" = "0" ] || [ "$1" = "off" ]; then

  echo "# DEACTIVATING ELECTRS"

  echo "# Stopping service"
  sleep 2s

  echo "# Disabling systemd service"
  sleep 1s

  echo "# Removing service file"
  sleep 1s

  echo "# Removing Tor Hidden Service"
  sleep 2s

  echo "# Closing firewall ports"
  sleep 1s

  echo "# OK ElectRS off."
  exit 0
fi

if [ "$1" = "update" ]; then
  echo "# Update Electrs"

  echo "# Checking for updates"
  sleep 2s

  echo "# Up-to-date on version ${ELECTRSVERSION}"
  sleep 1s

  echo "# Starting service"
  sleep 2s

  exit 0
fi

echo "# FAIL - Unknown Parameter $1"
exit 1
