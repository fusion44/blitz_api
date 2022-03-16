# TO MAKE THIS SCRIPT WORK:
# create the following file: scripts/sync_to_blitz.personal.sh (it will be ignored by git and not commited)
# add the following two lines to that files and fill with personal data of your development blitz:
localIP=""
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
    echo "FAIL: please make sure that sshpass is installed on your system"
    echo "macOS: brew install hudochenkov/sshpass/sshpass"
    exit 
fi

# check if localIP is available&responding
ping -c 1 $localIP
if [ "$?" != "0" ]; then
    echo "FAIL: was not able to ping $localIP"
    exit
fi

local=.
remote=admin@$localIP:/home/admin/blitz_api

# Needs sshpass installed
echo "# syncing local code to: ${remote}"
sshpass -p "$passwordA" rsync -re ssh $local $remote

# Restart the blitz service to activate changes
echo "# restarting blitzapi.service"
sshpass -p "$passwordA" ssh admin@$localIP 'sudo systemctl restart blitzapi.service'

# Get latest logs entries
echo "# latest log entries"
sshpass -p "$passwordA" ssh admin@$localIP 'sudo journalctl -u blitzapi.service -n 10 --no-pager --no-hostname'

# Watch the logs
echo "# watching logs - CTRL+C to exit"
sshpass -p "$passwordA" ssh admin@$localIP 'sudo journalctl -u blitzapi.service -f --no-hostname'