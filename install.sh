#!/bin/bash

# RAMSES RF Prometheus Exporter Installation Script

set -e

echo "RAMSES RF Prometheus Exporter Installation"
echo "=========================================="

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   echo "This script should not be run as root"
   exit 1
fi

# Check Python version
python_version=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
required_version="3.11"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "Error: Python 3.11 or higher is required. Found: $python_version"
    exit 1
fi

echo "✓ Python version check passed: $python_version"

# Check if ramses_rf module exists
if [ ! -d "/home/simon/src/3rd-party/ramses_rf" ]; then
    echo "Error: ramses_rf module not found at /home/simon/src/3rd-party/ramses_rf"
    echo "Please ensure the ramses_rf module is available at the expected location"
    exit 1
fi

echo "✓ ramses_rf module found"

# Install Python dependencies
echo "Installing Python dependencies..."
pip3 install -r requirements.txt

echo "✓ Dependencies installed"

# Make scripts executable
chmod +x ramses_prometheus_exporter.py
chmod +x test_exporter.py

echo "✓ Scripts made executable"

# Create ramses user and group if they don't exist
if ! id "ramses" &>/dev/null; then
    echo "Creating ramses user..."
    sudo useradd -r -s /bin/false ramses
    echo "✓ ramses user created"
else
    echo "✓ ramses user already exists"
fi

# Add current user to ramses group
if ! groups $USER | grep -q ramses; then
    echo "Adding current user to ramses group..."
    sudo usermod -a -G ramses $USER
    echo "✓ User added to ramses group"
    echo "Note: You may need to log out and back in for group changes to take effect"
else
    echo "✓ User already in ramses group"
fi

# Install systemd service
echo "Installing systemd service..."
sudo cp ramses-prometheus-exporter.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ramses-prometheus-exporter.service

echo "✓ Systemd service installed and enabled"

# Create log directory
sudo mkdir -p /var/log/ramses-exporter
sudo chown ramses:ramses /var/log/ramses-exporter

echo "✓ Log directory created"

# Test the installation
echo "Testing installation..."
python3 test_exporter.py &
TEST_PID=$!

# Wait a moment for the test to start
sleep 5

# Check if the test is running
if kill -0 $TEST_PID 2>/dev/null; then
    echo "✓ Test exporter started successfully"
    echo "You can check the metrics at http://localhost:8001/metrics"
    
    # Stop the test after 10 seconds
    sleep 10
    kill $TEST_PID 2>/dev/null || true
    echo "✓ Test completed"
else
    echo "✗ Test exporter failed to start"
    exit 1
fi

echo ""
echo "Installation completed successfully!"
echo ""
echo "Next steps:"
echo "1. Connect your RAMSES RF device (e.g., /dev/ttyUSB0)"
echo "2. Start the service: sudo systemctl start ramses-prometheus-exporter"
echo "3. Check status: sudo systemctl status ramses-prometheus-exporter"
echo "4. View logs: sudo journalctl -u ramses-prometheus-exporter -f"
echo "5. Access metrics: http://localhost:8000/metrics"
echo ""
echo "For Prometheus configuration, add the following to your prometheus.yml:"
echo "  - job_name: 'ramses-rf-exporter'"
echo "    static_configs:"
echo "      - targets: ['localhost:8000']"
echo ""
