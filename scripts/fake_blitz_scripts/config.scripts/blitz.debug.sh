#!/bin/bash

# USE THIS SCRIPT FOR BASIC SYSTEM STATUS DEBUG INFO

if [ "$1" == "redact" ]; then

  # get & check parameters
  redactFile=$2
  if [ "${redactFile}" == "" ]; then
    echo "# FAIL: missing second parameter"
    exit 1
  fi
  echo "# redacting file: ${redactFile}"
  if [ "${redactFile}" != "fakefile" ]; then
    echo "# FAIL: file does not exist"
    exit 1
  fi

  # redact nodeIDs
  echo "Redacting nodeIDs in ${redactFile}"

  # redact IPv4s
  echo "Redacting IPv4s in ${redactFile}"

  # redact onion addresses
  echo "Redacting onion addresses in ${redactFile}"

  # redact hostname
  echo "Redacting hostname in ${redactFile}"

  # redact balances
  echo "Redacting balances in ${redactFile}"

  # c-lightning self info in logs
  echo "Redacting c-lightning self info in ${redactFile}"

  # redact lnbits credentials
  echo "Redacting lnbits credentials in ${redactFile}"

  # redact i2p
  echo "Redacting i2p in ${redactFile}"

  exit 0
fi

# load code software version
echo "Loading code software version"
codeCommit="fakecommit"

## get basic info (its OK if not set yet)
echo "Loading basic info"
network="fakenetwork"
chain="fakechain"

echo
echo "***************************************************************"
echo "* RASPIBLITZ DEBUG LOGS "
echo "***************************************************************"
echo "blitzversion: fakeversion"
echo "commit-release: fakecommitrelease"
echo "commit-active: ${codeCommit}"
echo "chainnetwork: ${network} / ${chain}"
echo "uptime: fakeuptime"
echo

echo "*** FAILED SERVICES ***"
echo "list any services with problems: sudo systemctl list-units --failed"
echo "No failed services"
echo

echo "*** SETUPPHASE / BOOTSTRAP ***"
echo "see logs: cat /home/admin/raspiblitz.log"
echo "setupPhase--> fakesetupPhase"
echo "state--> fakestate"
echo "No setup phase issues"
echo

echo "*** BACKGROUNDSERVICE ***"
echo "to monitor Background service call: sudo journalctl -f -u background"
echo "Background service running smoothly"
echo

echo "*** BLOCKCHAIN (MAINNET) SYSTEMD STATUS ***"
echo "Blockchain mainnet service is active"
echo
echo "*** LAST BLOCKCHAIN (MAINNET) ERROR LOGS ***"
echo "No recent errors in blockchain mainnet logs"
echo
echo "*** LAST BLOCKCHAIN (MAINNET) INFO LOGS ***"
echo "Blockchain mainnet logs are clean"
echo

echo "*** LND (MAINNET) SYSTEMD STATUS ***"
echo "LND mainnet service is active"
echo
echo "*** LAST LND (MAINNET) ERROR LOGS ***"
echo "No recent errors in LND mainnet logs"
echo
echo "*** LAST LND (MAINNET) INFO LOGS ***"
echo "LND mainnet logs are clean"
echo

echo "*** CORE LIGHTNING (MAINNET) SYSTEMD STATUS ***"
echo "Core Lightning mainnet service is active"
echo
echo "*** LAST CORE LIGHTNING (MAINNET) INFO LOGS ***"
echo "Core Lightning mainnet logs are clean"
echo

echo "*** BLOCKCHAIN (TESTNET) SYSTEMD STATUS ***"
echo "Blockchain testnet service is active"
echo
echo "*** LAST BLOCKCHAIN (TESTNET) ERROR LOGS ***"
echo "No recent errors in blockchain testnet logs"
echo
echo "*** LAST BLOCKCHAIN (TESTNET) INFO LOGS ***"
echo "Blockchain testnet logs are clean"
echo

echo "*** LND (TESTNET) SYSTEMD STATUS ***"
echo "LND testnet service is active"
echo
echo "*** LAST LND (TESTNET) ERROR LOGS ***"
echo "No recent errors in LND testnet logs"
echo
echo "*** LAST LND (TESTNET) INFO LOGS ***"
echo "LND testnet logs are clean"
echo

echo "*** CORE LIGHTNING (TESTNET) SYSTEMD STATUS ***"
echo "Core Lightning testnet service is active"
echo
echo "*** LAST CORE LIGHTNING (TESTNET) INFO LOGS ***"
echo "Core Lightning testnet logs are clean"
echo

echo "*** BLOCKCHAIN (SIGNET) SYSTEMD STATUS ***"
echo "Blockchain signet service is active"
echo
echo "*** LAST BLOCKCHAIN (SIGNET) ERROR LOGS ***"
echo "No recent errors in blockchain signet logs"
echo
echo "*** LAST BLOCKCHAIN (SIGNET) INFO LOGS ***"
echo "Blockchain signet logs are clean"
echo

echo "*** LND (SIGNET) SYSTEMD STATUS ***"
echo "LND signet service is active"
echo
echo "*** LAST LND (SIGNET) ERROR LOGS ***"
echo "No recent errors in LND signet logs"
echo
echo "*** LAST LND (SIGNET) INFO LOGS ***"
echo "LND signet logs are clean"
echo

echo "*** CORE LIGHTNING (SIGNET) SYSTEMD STATUS ***"
echo "Core Lightning signet service is active"
echo
echo "*** LAST CORE LIGHTNING (SIGNET) INFO LOGS ***"
echo "Core Lightning signet logs are clean"
echo

echo "*** NGINX SYSTEMD STATUS ***"
echo "NGINX service is active"
echo

echo "*** LAST NGINX LOGS ***"
echo "No recent errors in NGINX logs"
echo "--> CHECK CONFIG: sudo nginx -t"
echo "NGINX configuration is valid"
echo

echo "*** BLITZAPI STATUS ***"
echo "BLITZAPI service is active"
echo
echo "*** LAST BLITZAPI LOGS ***"
echo "No recent errors in BLITZAPI logs"
echo

echo "*** BLITZ WebUI STATUS ***"
echo "BLITZ WebUI is active"
echo

echo "- TOUCHSCREEN is OFF by config"
echo

echo "- Loop is OFF by config"
echo

echo "- LND-RTL is OFF by config"
echo

echo "- CL-RTL is OFF by config"
echo

echo "- Electrum Rust Server is OFF by config"
echo

echo "- LIT is OFF by config"
echo

echo "- LNDg is OFF by config"
echo

echo "- BTCPayServer is OFF by config"
echo

echo "- BTC-RPC-Explorer is OFF by config"
echo

echo "- LNbits is OFF by config"
echo

echo "- Thunderhub is OFF by config"
echo

echo "- SPECTER is OFF by config"
echo

echo "- SPHINX is OFF by config"
echo

echo "- FINTS is OFF by config"
echo

echo "- PUBLICPOOL is OFF by config"
echo

echo "*** MOUNTED DRIVES ***"
echo "Fake drive information"
echo

echo "*** SD CARD HOMES ***"
echo "Fake SD card home information"
echo

echo "*** LOGFILES ***"
echo "Fake log file information"
echo

echo "*** DATADRIVE ***"
echo "Fake data drive information"
echo

echo "*** NETWORK ***"
echo "Fake network information"
echo

echo "*** ZRAM ***"
echo "Fake ZRAM information"
echo

echo "*** HARDWARE TEST RESULTS ***"
echo "Fake hardware test results"
echo

echo "*** SYSTEM CACHE STATUS ***"
echo "Fake system cache status"
echo

echo "*** POSSIBLE ERROR REPORTS ***"
echo "No error reports found"
echo

echo "*** OPTION: SHARE THIS DEBUG OUTPUT ***"
echo "An easy way to share this debug output on GitHub or on a support chat"
echo "Use the following command and share the resulting link using termbin.com service and tor proxy:"
echo " debug -l"
echo "If tor is failing and you don't mind leaking your ip address to the termbin service, use without tor:"
echo " debug -l -n"
echo
