# Warning

______________________________________________________________________

Heavy use of vibe coding involved, this project is mostly me testing workflows around AI more than
actually delivering working code. YMMV, no warranties, not reviewed, past results do not guarantee
future results, contact a doctor if it lasts longer than 4 hours.

______________________________________________________________________

# Honeywell Radio Exporter

A Python module that uses the `ramses_rf` library to listen to RAMSES RF messages and expose metrics
for Prometheus to scrape.

## Features

- **Message Tracking**: Counts and categorizes all RAMSES RF messages by type, verb, and code
- **Device Communication**: Monitors communications between different devices
- **System State**: Tracks active devices, message rates, and timestamps
- **Performance Metrics**: Measures processing duration and payload sizes
- **Error Monitoring**: Counts and categorizes processing errors
- **Prometheus Integration**: Standard HTTP metrics endpoint for scraping

## Installation

### Prerequisites

- Python 3.11 or higher
- A USB-to-RF device (Honeywell HGI80 or ESP32 with evofw3 firmware)
- The `ramses_rf` module available at `/home/simon/src/3rd-party/ramses_rf`

### Development Setup

1. **Clone and navigate to the project**:

   ```bash
   cd /home/simon/src/development/honeywell-radio-exporter
   ```

1. **Install dependencies**:

   ```bash
   pip install -e .
   pip install -e ".[dev]"
   ```

1. **Install the ramses_rf module**:

   ```bash
   cd /home/simon/src/3rd-party/ramses_rf
   pip install -e .
   ```

## Testing

### Running Tests with Tox

The project uses `tox` for comprehensive testing across multiple Python versions and tools:

```bash
# Run all test environments
tox

# Run specific environments
tox -e py311          # Python 3.11 tests
tox -e lint           # Linting checks
tox -e format         # Code formatting checks
tox -e security       # Security checks
tox -e coverage       # Coverage report
```

### Running Tests Manually

```bash
# Run unit tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=honeywell_radio_exporter --cov-report=html

# Run linting
pylint honeywell_radio_exporter/
flake8 honeywell_radio_exporter/
black --check honeywell_radio_exporter/
isort --check-only honeywell_radio_exporter/

# Run type checking
mypy honeywell_radio_exporter/

# Run security checks
bandit -r honeywell_radio_exporter/
```

### Using the Test Runner

For convenience, use the included test runner:

```bash
python run_tests.py
```

This will run all tests and provide a summary of results.

## Code Quality Tools

The project includes several code quality tools:

- **pytest**: Unit testing framework
- **pylint**: Code analysis and style checking
- **flake8**: Style guide enforcement
- **black**: Code formatting
- **isort**: Import sorting
- **mypy**: Static type checking
- **bandit**: Security vulnerability scanning
- **coverage**: Code coverage reporting

## Usage

### Basic Usage

```bash
# Start with RAMSES RF device
python -m honeywell_radio_exporter --ramses-port /dev/ttyUSB0

# Start with custom port
python -m honeywell_radio_exporter --ramses-port /dev/ttyUSB0 --port 9090

# Start with debug logging
python -m honeywell_radio_exporter --ramses-port /dev/ttyUSB0 --log-level DEBUG

# Alternative: using the installed script
honeywell-radio-exporter --ramses-port /dev/ttyUSB0
```

### As a Service

```bash
# Install the service
sudo cp honeywell_radio_exporter/ramses-prometheus-exporter.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ramses-prometheus-exporter

# Start the service
sudo systemctl start ramses-prometheus-exporter

# Check status
sudo systemctl status ramses-prometheus-exporter
```

## Configuration

### Prometheus Configuration

Add to your `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'honeywell-radio-exporter'
    static_configs:
      - targets: ['localhost:8000']
    scrape_interval: 10s
    metrics_path: /metrics
```

## Available Metrics

- `ramses_messages_total`: Total number of RAMSES messages received
- `ramses_message_types_total`: Total number of messages by type
- `ramses_device_communications_total`: Total number of communications between devices
- `ramses_active_devices`: Number of active devices in the system
- `ramses_last_message_timestamp`: Timestamp of the last message received
- `ramses_message_rate`: Messages per second over the last minute
- `ramses_message_processing_duration_seconds`: Time spent processing messages
- `ramses_message_errors_total`: Total number of message processing errors
- `ramses_message_payload_size_bytes`: Size of message payloads
- `ramses_device_temperature_celsius`: Temperature reading per device in Celsius
- `ramses_device_setpoint_celsius`: Target temperature setpoint per device/zone
- `ramses_device_info`: Device information (ID to name mapping)
- `ramses_device_last_seen_timestamp`: Last message timestamp per device
- `ramses_zone_info`: Zone information (zone index to zone name mapping)
- `ramses_zone_window_open`: Window open state per zone (0=closed, 1=open)
- `ramses_zone_mode_info`: Zone operating mode information
- `ramses_heat_demand`: Heat demand per zone (0.0-1.0 = 0-100%)
- `ramses_system_sync_remaining_seconds`: Seconds until next system sync
- `ramses_system_sync_last_timestamp`: Last system sync message timestamp
- `ramses_boiler_messages_sent_total`: Total messages sent to boilers
- `ramses_boiler_messages_received_total`: Total messages received from boilers
- `ramses_boiler_last_seen_timestamp`: Last message from boiler
- `ramses_boiler_last_contacted_timestamp`: Last message sent to boiler
- `ramses_boiler_setpoint_celsius`: Current boiler setpoint temperature
- `ramses_boiler_modulation_level`: Current boiler modulation level (0.0-1.0)
- `ramses_boiler_flame_active`: Boiler flame status (0=off, 1=on)
- `ramses_boiler_ch_active`: Central heating active status (0=off, 1=on)
- `ramses_boiler_dhw_active`: Domestic hot water active status (0=off, 1=on)
- `ramses_system_info`: Information about the RAMSES RF system

## Development

### Project Structure

```
honeywell-radio-exporter/
├── honeywell_radio_exporter/          # Main package
│   ├── __init__.py
│   ├── ramses_prometheus_exporter.py
│   └── requirements.txt
├── tests/                       # Test files
│   └── test_exporter.py
├── tox.ini                      # Tox configuration
├── pyproject.toml              # Project configuration
├── .pylintrc                   # Pylint configuration
├── run_tests.py                # Test runner script
└── README.md                   # This file
```

### Adding New Tests

1. Create test functions in `tests/test_exporter.py`
1. Use pytest fixtures and markers as needed
1. Run tests with `pytest tests/ -v`

### Code Style

The project follows PEP 8 with some modifications:

- Line length: 88 characters (Black default)
- Use Black for formatting
- Use isort for import sorting
- Follow pylint recommendations

### Pre-commit Hooks

Consider setting up pre-commit hooks for automatic code quality checks:

```bash
pip install pre-commit
pre-commit install
```

## Troubleshooting

### Common Issues

1. **Import errors**: Ensure the `ramses_rf` module is properly installed
1. **Permission errors**: Check USB device permissions
1. **Test failures**: Run `tox -e py311` to see detailed error messages

### Debug Mode

Run with debug logging for detailed information:

```bash
python -m honeywell_radio_exporter --ramses-port /dev/ttyUSB0 --log-level DEBUG
```

## Contributing

1. Fork the repository
1. Create a feature branch
1. Make your changes
1. Run tests: `python run_tests.py`
1. Submit a pull request

## License

This project is licensed under the MIT License.
