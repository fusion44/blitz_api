# Set the IP of the Raspiblitz
ip=192.168.1.254

# admin password, WARNING only use with a dev machine
password="your_pw_here"

local=.
remote=admin@$ip:/home/admin/blitz_api

# Needs sshpass installed
sshpass -p "$password" rsync -re ssh --progress $local $remote