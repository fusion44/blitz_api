#!/bin/bash

# Based on: https://gist.github.com/normandmickey/3f10fc077d15345fb469034e3697d0d0

# https://github.com/dgarage/NBXplorer/tags
NBXplorerVersion="v2.5.2"
# https://github.com/btcpayserver/btcpayserver/releases
BTCPayVersion="v1.13.0"

# check who signed the release (person that published release)
#PGPsigner="nicolasdorier"
#PGPpubkeyLink="https://keybase.io/nicolasdorier/pgp_keys.asc"
#PGPpubkeyFingerprint="AB4CFA9895ACA0DBE27F6B346618763EF09186FE"
# ---
#PGPsigner="Kukks"
#PGPpubkeyLink="https://github.com/${PGPsigner}.gpg"
#PGPpubkeyFingerprint="8E5530D9D1C93097"
# ---
PGPsigner="web-flow"
PGPpubkeyLink="https://github.com/web-flow.gpg"
PGPpubkeyFingerprint="B5690EEEBB952194"


if [ "$1" = "status" ]; then

  echo "version='${BTCPayVersion}'"
  echo "prepared=1"
  echo "installed=1"

  echo "switchedon=1"
  echo "localIP='192.168.1.18'"
  echo "httpPort='23000'"
  echo "httpsPort='23001'"
  echo "httpsForced='1'"
  echo "httpsSelfsigned='1'" # TODO: change later if IP2Tor+LetsEncrypt is active
  echo "authMethod='userdefined'"
  echo "publicIP='12.18.3.38'"

  echo "toraddress=dsfkjsdmflidsug"
  echo "sslFingerprintTOR=siawes;lgjsa;fgi"
  exit 0
fi


########################################
# UNINSTALL (remove from system)
########################################

if [ "$1" = "uninstall" ]; then

  echo "unistalling btcpay"
  sleep 10s
  echo "# uninstall done"

  exit 0
fi

########################################
# ON (activate & config)
########################################

if [ "$1" = "1" ] || [ "$1" = "on" ]; then

  echo "# create btcpay user"
  sleep 2s

  echo "# install .NET"
  echo "Downloading .NET"
  sleep 2s

  # NBXplorer
  echo "# Install NBXplorer $NBXplorerVersion"
  echo "# Download the NBXplorer source code $NBXplorerVersion"
  sleep 3s
  echo "# OK - git clone of NBXplorer successful."
  echo "# Build NBXplorer $NBXplorerVersion"

  # BTCPayServer
  echo "# Install BTCPayServer"
  echo "# Download the BTCPayServer source code $BTCPayVersion"
  sleep 2s
  echo "# Downloaded the BTCPayServer source code $BTCPayVersion"

  echo "# Build BTCPayServer $BTCPayVersion"
  sleep 10s
  echo "result='OK'"
  exit 0
fi

########################################
# OFF (deactivate)
########################################

if [ "$1" = "0" ] || [ "$1" = "off" ]; then

  echo "unistalling btcpay"
  sleep 10s

  echo "# deleting data"

  sleep 2s
  echo "# uninstall done"

  sleep 10s
  echo "# OK BTCPayServer deactivated."

  # needed for API/WebUI as signal that install ran thru
  echo "result='OK'"

  exit 0
fi
