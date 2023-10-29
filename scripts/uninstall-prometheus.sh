#!/bin/bash

# Close ports
sudo ufw deny 9090,9100,9256/tcp

# Stop Prometheus, Node Exporter, and Process Exporter services
sudo systemctl stop prometheus
sudo systemctl stop node_exporter
sudo systemctl stop process_exporter

# Disable Prometheus, Node Exporter, and Process Exporter services
sudo systemctl disable prometheus
sudo systemctl disable node_exporter
sudo systemctl disable process_exporter

# Remove the service files
sudo rm /etc/systemd/system/prometheus.service
sudo rm /etc/systemd/system/node_exporter.service
sudo rm /etc/systemd/system/process_exporter.service

# Reload systemd daemon to reflect changes
sudo systemctl daemon-reload
sudo systemctl reset-failed

# Remove binaries
sudo rm /usr/local/bin/prometheus
sudo rm /usr/local/bin/promtool
sudo rm /usr/local/bin/node_exporter
sudo rm /usr/local/bin/process-exporter

# Remove configuration and data directories
sudo rm -r /etc/prometheus
sudo rm -r /var/lib/prometheus

# Remove Prometheus system user
sudo userdel prometheus


# Print completion status
echo "Prometheus, Node Exporter, and Process Exporter have been removed."
