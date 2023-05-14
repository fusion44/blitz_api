#!/bin/bash

# Help function
show_help() {
    echo
    echo "Usage: $0 [enable|disable|help] [port]"
    echo ""
    echo "Options:"
    echo "  enable:   Open the specified port (default is 5678), install debugpy Python package, and set remote_debugging to true in .env_sample"
    echo "  disable:  Close the specified port (default is 5678), uninstall debugpy Python package, and set remote_debugging to false in .env_sample"
    echo "  help:     Show this help message"
    echo "  port:     The port number to open/close (default is 5678)"
    echo ""
    echo "This script must be run as the user 'blitzapi' from the /home/blitzapi/blitz_api directory."
}

# Check if help is requested
if [ "$1" == "help" ]; then
    show_help
    exit 0
fi

# Check if the script is running from the correct directory
if [ "$(pwd)" != "/home/blitzapi/blitz_api" ]; then
    echo "This script must be run from /home/blitzapi/blitz_api"
    exit 1
fi

# Check if the script is running as the correct user
if [ "$(whoami)" != "blitzapi" ]; then
    echo "This script must be run as blitzapi"
    exit 1
fi

# Check if an action is provided as a parameter
if [ -z "$1" ] || ( [ "$1" != "enable" ] && [ "$1" != "disable" ] ); then
    echo "You must specify an action: 'enable' to open the port and install debugpy, or 'disable' to close the port and uninstall debugpy"
    exit 1
fi


update_env_file() {
    echo "Updating .env_sample file $1"
    if [ "$1" == "enable" ]; then
        # Uncomment the line and set to true
        sed -i "s/^# remote_debugging=.*/remote_debugging=true/g" /home/blitzapi/blitz_api/.env_sample
    else
        # Comment the line and set to false
        sed -i "s/^remote_debugging=.*/# remote_debugging=false/g" /home/blitzapi/blitz_api/.env_sample
    fi
}

# Default port
PORT=5678

# Check if a port number is provided as a parameter
if [ -n "$2" ]; then
    PORT=$2
fi

# Ask for user confirmation
echo "You are about to $1 remote debugging on port $PORT."
echo "Enabling will open the port $PORT and install the debugpy package."
echo "Disabling will reverse these operations."
if [ "$1" == "enable" ]; then
    echo
    echo "Make sure that remote_debugging is set to true in .env_sample. Reason is that RaspiBlitz copies the sample '.env_sample' to a fresh '.env' file on each restart."
    echo
fi
read -p "Do you want to proceed? (y/n) " -n 1 -r
echo    # move to a new line
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    echo "Operation cancelled by the user."
    exit 1
fi

update_env_file $1

# Activate the virtual environment
source /home/blitzapi/blitz_api/venv/bin/activate

# If the user confirmed
if [ "$1" == "enable" ]; then
    # Install debugpy python package
    pip install debugpy

    # Open the port
    echo "Opening port $PORT"
    sudo ufw allow $PORT/tcp

    echo "Port $PORT is open and debugpy is installed"
else
    # Uninstall debugpy python package
    pip uninstall -y debugpy

    # Close the port
    echo "Closing port $PORT"
    sudo ufw delete allow $PORT/tcp

    echo "Port $PORT is closed and debugpy is uninstalled"
fi

# Deactivate the virtual environment
deactivate

echo "Restarting Blitz API"
sudo systemctl restart blitzapi.service
