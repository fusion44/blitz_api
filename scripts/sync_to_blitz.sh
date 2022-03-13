# Set the IP of the Raspiblitz
ip=192.168.1.254

# admin password, WARNING only use with a dev machine
password="your_pw_here"

local=.
remote=admin@$ip:/home/admin/blitz_api

# Needs sshpass installed
sshpass -p "$password" rsync -re ssh $local $remote

# Restart the blitz service to activate changes
sshpass -p "$password" ssh admin@$ip 'sudo systemctl restart blitzapi.service'

# Get latest logs entries
sshpass -p "$password" ssh admin@$ip 'sudo journalctl -u blitzapi.service -n 10 --no-pager --no-hostname'

# Watch the logs
sshpass -p "$password" ssh admin@$ip 'sudo journalctl -u blitzapi.service -f --no-hostname'