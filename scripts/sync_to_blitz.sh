# TO MAKE THIS SCRIPT WORK:
# create the following file: scripts/sync_to_blitz.personal.sh (it will be ignored by git and not commited)
# add the following two lines to that files and fill with personal data of your development blitz:
localIP=""
sshPort="22"
passwordA=""

# get personal blitz info
source scripts/sync_to_blitz.personal.sh
if [ "${localIP}" = "" ] || [ "${passwordA}" == "" ]; then
    echo "FAIL: please create scripts/sync_to_blitz.personal.sh file with localIP & passwordA info."
    exit
fi

# check if sshpass is installed
sshpassInstalled=$(sshpass -V | grep -c "sshpass")
if [ ${sshpassInstalled} -eq 0 ]; then
    echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    echo "FAIL: please make sure that sshpass is installed on your system"
    echo "macOS: brew install hudochenkov/sshpass/sshpass"
    echo "Linux(Debian): apt install sshpass"
    exit
fi

# check if ping is installed
pingInstalled=$(ping -c 1 1.1.1.1 | grep -c "PING")
if [ ${pingInstalled} -eq 0 ]; then
    echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    echo "FAIL: please make sure that ping is installed on your system"
    echo "Linux(Debian): apt install inetutils-ping OR apt install iputils-ping"
    exit
fi

# check if localIP is available&responding
ping -c 1 $localIP
if [ "$?" != "0" ]; then
    echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    echo "FAIL: was not able to ping $localIP"
    exit
fi

local=.
remote=admin@$localIP:/root/blitz_api

# Needs sshpass installed
echo "# syncing local code to: ${remote}"
sshpass -p "$passwordA" rsync -rvz -e "ssh -p ${sshPort}" $local $remote
result=$?
echo "result(${result})"
if [ "$result" != "0" ]; then
    echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    echo "FAIL: was not able to ssh in: ssh -p ${sshPort} admin@$localIP"
    echo "SSH in once manually. Then try again."
    exit 1
fi

# Restart the blitz service to activate changes
echo "# restarting blitzapi.service"
sshpass -p "$passwordA" ssh -p $sshPort admin@$localIP 'sudo systemctl restart blitzapi.service'

# Get latest logs entries
echo "# latest log entries"
sshpass -p "$passwordA" ssh -p $sshPort admin@$localIP 'sudo journalctl -u blitzapi.service -n 10 --no-pager --no-hostname'

# Watch the logs
echo "# watching logs - CTRL+C to exit"
sshpass -p "$passwordA" ssh -p $sshPort admin@$localIP 'sudo journalctl -u blitzapi.service -f --no-hostname'
