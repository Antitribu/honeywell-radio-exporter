# RAMSES RF Prometheus Exporter - Summary

## What Was Created

I've created a complete Python3 module that uses the `ramses_rf` module to listen to RAMSES RF
messages and expose metrics for Prometheus to scrape. Here's what was delivered:

### Core Files

1. **`ramses_prometheus_exporter.py`** - Main exporter module

   - Integrates with the `ramses_rf` module from `/home/simon/src/3rd-party/ramses_rf`
   - Listens to RAMSES RF messages and captures comprehensive metrics
   - Exposes Prometheus metrics via HTTP endpoint
   - Includes command-line interface for configuration

1. **`requirements.txt`** - Python dependencies

   - Prometheus client library
   - RAMSES RF dependencies
   - Additional required packages

1. **`test_exporter.py`** - Test script

   - Tests the exporter without requiring actual hardware
   - Validates metrics creation and basic functionality
   - Can be run to verify installation

### Configuration Files

4. **`prometheus.yml`** - Prometheus configuration

   - Example configuration for scraping the exporter
   - Includes proper labeling and scraping intervals

1. **`ramses-prometheus-exporter.service`** - Systemd service

   - For easy deployment as a system service
   - Includes security settings and proper user/group configuration

1. **`install.sh`** - Installation script

   - Automated installation and setup
   - Creates necessary users and groups
   - Tests the installation

### Visualization

7. **`grafana-dashboard.json`** - Grafana dashboard

   - Pre-configured dashboard for visualizing RAMSES RF metrics
   - Includes panels for message rates, device communications, errors, etc.

1. **`README.md`** - Comprehensive documentation

   - Installation instructions
   - Usage examples
   - Troubleshooting guide
   - Available metrics documentation

## Key Features

### Metrics Captured

- **Message Counters**: Total messages, message types, device communications
- **System State**: Active devices, message timestamps, message rates
- **Performance**: Message processing duration, payload sizes
- **Errors**: Message processing errors with categorization
- **System Info**: Gateway version, device counts, last message details

### Prometheus Integration

- HTTP endpoint at `/metrics` for Prometheus scraping
- Proper metric types (Counters, Gauges, Histograms, Info)
- Rich labeling for detailed analysis
- Standard Prometheus format

### Message Processing

- Intercepts all RAMSES RF messages via enhanced message handler
- Categorizes messages by type, verb, code, and device
- Tracks device-to-device communications
- Monitors system performance and errors

## Usage Examples

### Basic Usage

```bash
# Start with RAMSES RF device
python3 ramses_prometheus_exporter.py --ramses-port /dev/ttyUSB0

# Start with custom port
python3 ramses_prometheus_exporter.py --ramses-port /dev/ttyUSB0 --port 9090

# Start with debug logging
python3 ramses_prometheus_exporter.py --ramses-port /dev/ttyUSB0 --log-level DEBUG
```

### Installation

```bash
# Run the installation script
./install.sh

# Start the service
sudo systemctl start ramses-prometheus-exporter

# Check status
sudo systemctl status ramses-prometheus-exporter
```

### Testing

```bash
# Test without hardware
python3 test_exporter.py

# Check metrics endpoint
curl http://localhost:8000/metrics
```

## Prometheus Queries

### Message Rate

```promql
rate(ramses_messages_total[5m])
```

### Most Active Devices

```promql
topk(5, sum by (source_device) (ramses_device_communications_total))
```

### Error Rate

```promql
rate(ramses_message_errors_total[5m])
```

### Average Processing Time

```promql
histogram_quantile(0.95, rate(ramses_message_processing_duration_seconds_bucket[5m]))
```

## Architecture

The exporter follows a clean architecture:

1. **Gateway Layer**: Connects to RAMSES RF hardware
1. **Message Handler**: Intercepts and processes messages
1. **Metrics Layer**: Captures and categorizes data
1. **HTTP Server**: Exposes metrics for Prometheus
1. **Configuration**: Command-line and service management

## Integration Points

- **ramses_rf Module**: Uses the existing module at `/home/simon/src/3rd-party/ramses_rf`
- **Prometheus**: Standard HTTP metrics endpoint
- **Grafana**: Pre-configured dashboard for visualization
- **Systemd**: Service management for production deployment

## Next Steps

1. **Install Dependencies**: `pip install -r requirements.txt`
1. **Run Installation**: `./install.sh`
1. **Connect Hardware**: Attach RAMSES RF device
1. **Start Service**: `sudo systemctl start ramses-prometheus-exporter`
1. **Configure Prometheus**: Add the job to your prometheus.yml
1. **Import Dashboard**: Import the Grafana dashboard for visualization

The module is production-ready and includes comprehensive error handling, logging, and monitoring
capabilities.
