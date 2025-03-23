#!/bin/bash

# https://github.com/openoms/joininbox/tags
JBTAG="v0.8.3" # installs JoinMarket v0.9.11


if [ "$1" = "status" ]; then
  sleep 2s
  echo "version='v0.9.11'"
  echo "installed=1"
  echo "jbversion='${JBTAG}'"
  echo "localIP='192.168.1.18'"
  echo "toraddress='joinmarketxyzabcdefghijk.onion'"
  exit 0
fi


########################################
# ON (activate & config)
########################################

if [ "$1" = "1" ] || [ "$1" = "on" ]; then

  echo "# ACTIVATING JOINMARKET"

  echo "# Checking Tor status"
  sleep 1s
  echo "# OK, running behind Tor"

  echo "# Setting password for joinmarket user"
  sleep 2s

  echo "# Creating data directory on HDD"
  sleep 1s

  echo "# Setting up autostart configuration"
  sleep 2s

  echo "# Checking bitcoin.conf settings"
  sleep 1s
  echo "# Added 'deprecatedrpc=create_bdb' to bitcoin.conf"

  echo "# Ensuring Bitcoin Core wallet is enabled"
  sleep 2s

  echo "# Creating non-descriptor wallet.dat"
  sleep 3s

  echo "# Configuring JoinMarket"
  sleep 5s

  echo "# Start to use by logging in to the 'joinmarket' user with:"
  echo "# 'sudo su joinmarket' or use the shortcut 'jm'"

  exit 0
fi

########################################
# OFF (deactivate)
########################################

if [ "$1" = "0" ] || [ "$1" = "off" ]; then

  echo "# DEACTIVATING JOINMARKET"

  echo "# Removing the joinmarket user"
  sleep 3s

  echo "# Deactivating related services"
  sleep 2s

  echo "# JoinMarket successfully removed"

  exit 0
fi

echo "FAIL - Unknown Parameter $1"
echo "may need reboot to run"
exit 1
