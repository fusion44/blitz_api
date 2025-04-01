#!/bin/bash

# https://github.com/Ride-The-Lightning/RTL/releases
RTLVERSION="v0.15.2"

if [ "$1" = "status" ]; then
  sleep 2s
  # raise a fake error
  echo "result='FAKE ERROR FOR TESTING'" >&2
  exit 1

  # get LNTYPE and CHAIN parameters
  LNTYPE="$2" # lnd or cl
  CHAIN="$3" # mainnet or testnet or signet

  # set defaults if not specified
  if [ "${LNTYPE}" == "" ]; then
    LNTYPE="lnd"
  fi
  if [ "${CHAIN}" == "" ]; then
    CHAIN="mainnet"
  fi

  # construct port based on implementation
  if [ "${LNTYPE}" == "cl" ]; then
    RTLHTTP=7000
  elif [ "${LNTYPE}" == "lnd" ]; then
    RTLHTTP=3000
  fi

  echo "version='${RTLVERSION}'"
  echo "installed='1'"
  echo "localIP='192.168.1.18'"
  echo "httpPort='${RTLHTTP}'"
  echo "httpsPort='$((RTLHTTP + 1))'"
  echo "httpsForced='0'"
  echo "httpsSelfsigned='1'"
  echo "authMethod='password_b'"
  echo "toraddress='${LNTYPE}rtl43rf3wdasxcvbnmuytre.onion'"
  exit 0
fi


########################################
# ON (activate & config)
########################################

if [ "$1" = "1" ] || [ "$1" = "on" ]; then
  # get LNTYPE and CHAIN parameters
  LNTYPE="$2" # lnd or cl
  CHAIN="$3" # mainnet or testnet or signet

  # set defaults if not specified
  if [ "${LNTYPE}" == "" ]; then
    LNTYPE="lnd"
  fi
  if [ "${CHAIN}" == "" ]; then
    CHAIN="mainnet"
  fi

  # construct port based on implementation
  if [ "${LNTYPE}" == "cl" ]; then
    RTLHTTP=7000
    systemdService="cRTL"
  elif [ "${LNTYPE}" == "lnd" ]; then
    RTLHTTP=3000
    systemdService="RTL"
  fi

  echo "# Activating RTL for ${LNTYPE} ${CHAIN}"

  echo "# Setting up service permissions"
  sleep 2s

  echo "# Updating firewall rules"
  sleep 1s

  echo "# Creating systemd service: ${systemdService}.service"
  sleep 2s

  if [ "${LNTYPE}" == "cl" ]; then
    echo "# Setting up CLN REST plugin"
    sleep 2s
  fi

  echo "# Setting up NGINX"
  sleep 3s

  echo "# Configuring Tor Hidden Service"
  sleep 2s

  echo "# Enabling and starting service"
  sleep 3s

  echo "# OK - the ${systemdService}.service is now enabled & started"
  echo "result='OK'"
  exit 0
fi

########################################
# OFF (deactivate)
########################################

if [ "$1" = "0" ] || [ "$1" = "off" ]; then
  LNTYPE="$2" # lnd or cl
  CHAIN="$3" # mainnet or testnet or signet

  # set defaults if not specified
  if [ "${LNTYPE}" == "" ]; then
    LNTYPE="lnd"
  fi
  if [ "${CHAIN}" == "" ]; then
    CHAIN="mainnet"
  fi

  # construct port based on implementation
  if [ "${LNTYPE}" == "cl" ]; then
    RTLHTTP=7000
    systemdService="cRTL"
  elif [ "${LNTYPE}" == "lnd" ]; then
    RTLHTTP=3000
    systemdService="RTL"
  fi

  echo "# Removing RTL for ${LNTYPE} ${CHAIN}"

  echo "# Stopping service"
  sleep 2s

  echo "# Removing configuration"
  sleep 1s

  echo "# Removing NGINX configurations"
  sleep 2s

  echo "# Removing Tor Hidden Service"
  sleep 2s

  echo "# Disabling service"
  sleep 1s

  echo "# Removing service file"
  sleep 1s

  echo "# Closing firewall ports"
  sleep 1s

  echo "# OK ${systemdService} removed."
  echo "result='OK'"
  exit 0
fi

########################################
# UPDATE
########################################

if [ "$1" = "update" ]; then
  echo "# UPDATING RTL"

  updateOption="$2"
  if [ ${#updateOption} -eq 0 ]; then
    echo "# Checking for updates"
    sleep 2s
    echo "# You are up-to-date on version ${RTLVERSION}"
  elif [ "$updateOption" = "commit" ]; then
    echo "# Updating to latest commit"
    sleep 2s
    echo "# Pulling latest changes"
    sleep 3s
    echo "# Running npm install"
    sleep 5s
    echo "# Updated RTL to latest commit"
  else
    echo "# Unknown option: $updateOption"
  fi

  echo "# Starting the RTL service"
  sleep 2s
  exit 0
fi

echo "# may need reboot to run normal again"
exit 1
