#!/bin/bash

# Update package repositories
sudo apt-get update

# Install necessary tools
sudo apt-get install -y curl tar

# Define versions to install
PROMETHEUS_VERSION="2.45.0"
NODE_EXPORTER_VERSION="1.6.0"
PROCESS_EXPORTER_VERSION="0.7.10"

# Get machine architecture
MACHINE_ARCH=$(uname -m)
if [ "${MACHINE_ARCH}" == "x86_64" ]; then
    ARCH="amd64"
elif [ "${MACHINE_ARCH}" == "aarch64" ]; then
    ARCH="arm64"
else
    echo "Unsupported architecture"
    exit 1
fi

# Create Prometheus system user
sudo useradd --no-create-home --shell /bin/false prometheus

# Create necessary directories
sudo mkdir /etc/prometheus
sudo mkdir /var/lib/prometheus

# Install Prometheus
curl -Lo prometheus.tar.gz https://github.com/prometheus/prometheus/releases/download/v${PROMETHEUS_VERSION}/prometheus-${PROMETHEUS_VERSION}.linux-${ARCH}.tar.gz
tar xvf prometheus.tar.gz
sudo cp prometheus-${PROMETHEUS_VERSION}.linux-${ARCH}/prometheus /usr/local/bin/
sudo cp prometheus-${PROMETHEUS_VERSION}.linux-${ARCH}/promtool /usr/local/bin/
sudo cp -r prometheus-${PROMETHEUS_VERSION}.linux-${ARCH}/consoles /etc/prometheus
sudo cp -r prometheus-${PROMETHEUS_VERSION}.linux-${ARCH}/console_libraries /etc/prometheus
rm -rf prometheus-${PROMETHEUS_VERSION}.linux-${ARCH}*
sudo chown prometheus:prometheus /usr/local/bin/prometheus
sudo chown prometheus:prometheus /usr/local/bin/promtool
sudo chown -R prometheus:prometheus /etc/prometheus/consoles
sudo chown -R prometheus:prometheus /etc/prometheus/console_libraries
sudo chown -R prometheus:prometheus /var/lib/prometheus

# Install Node Exporter
curl -Lo node_exporter.tar.gz https://github.com/prometheus/node_exporter/releases/download/v${NODE_EXPORTER_VERSION}/node_exporter-${NODE_EXPORTER_VERSION}.linux-${ARCH}.tar.gz
tar xvf node_exporter.tar.gz
sudo cp node_exporter-${NODE_EXPORTER_VERSION}.linux-${ARCH}/node_exporter /usr/local/bin/
rm -rf node_exporter-${NODE_EXPORTER_VERSION}.linux-${ARCH}*
sudo chown prometheus:prometheus /usr/local/bin/node_exporter

# Install Process Exporter
curl -Lo process_exporter.tar.gz https://github.com/ncabatoff/process-exporter/releases/download/v${PROCESS_EXPORTER_VERSION}/process-exporter-${PROCESS_EXPORTER_VERSION}.linux-${ARCH}.tar.gz
tar xvf process_exporter.tar.gz
sudo cp process-exporter-${PROCESS_EXPORTER_VERSION}.linux-${ARCH}/process-exporter /usr/local/bin/
rm -rf process-exporter-${PROCESS_EXPORTER_VERSION}.linux-${ARCH}*
sudo chown prometheus:prometheus /usr/local/bin/process-exporter

# Create Process Exporter configuration file
cat << EOF | sudo tee /etc/prometheus/process-exporter.yaml
process_names:
  - name: "{{.Comm}}"
    cmdline:
    - '.+'
user:
  - name: redis
  - name: blitzapi
  - name: bitcoin

EOF

# Create Prometheus configuration file
cat << EOF | sudo tee /etc/prometheus/prometheus.yml
global:
  scrape_interval:     15s
  evaluation_interval: 15s
scrape_configs:
  - job_name: 'prometheus'
    static_configs:
    - targets: ['localhost:9090']
  - job_name: 'node_exporter'
    static_configs:
    - targets: ['localhost:9100']
  - job_name: 'process_exporter'
    static_configs:
    - targets: ['localhost:9256']
EOF

# Create Prometheus, Node Exporter, and Process Exporter service files
cat << EOF | sudo tee /etc/systemd/system/prometheus.service
[Unit]
Description=Prometheus
Wants=network-online.target
After=network-online.target

[Service]
User=prometheus
Group=prometheus
Type=simple
ExecStart=/usr/local/bin/prometheus \
    --config.file /etc/prometheus/prometheus.yml \
    --storage.tsdb.path /var/lib/prometheus/ \
    --web.console.templates=/etc/prometheus/consoles \
    --web.console.libraries=/etc/prometheus/console_libraries

[Install]
WantedBy=multi-user.target
EOF

cat << EOF | sudo tee /etc/systemd/system/node_exporter.service
[Unit]
Description=Node Exporter
Wants=network-online.target
After=network-online.target

[Service]
User=prometheus
Group=prometheus
Type=simple
ExecStart=/usr/local/bin/node_exporter

[Install]
WantedBy=multi-user.target
EOF

cat << EOF | sudo tee /etc/systemd/system/process_exporter.service
[Unit]
Description=Process Exporter
Wants=network-online.target
After=network-online.target

[Service]
User=prometheus
Group=prometheus
Type=simple
ExecStart=/usr/local/bin/process-exporter \
    --config.path /etc/prometheus/process-exporter.yaml

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd, enable & start Prometheus, Node Exporter, and Process Exporter services
sudo systemctl daemon-reload
sudo systemctl start prometheus
sudo systemctl enable prometheus
sudo systemctl start node_exporter
sudo systemctl enable node_exporter
sudo systemctl start process_exporter
sudo systemctl enable process_exporter

sudo ufw allow 9090,9100,9256/tcp

echo "Prometheus, Node Exporter, and Process Exporter installed successfully!"
