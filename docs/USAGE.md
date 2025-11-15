# How to Run Honeywell Radio Exporter

## Quick Start

### Basic Usage (with RAMSES RF device)

```bash
# Activate virtual environment
source venv/bin/activate

# Run with default settings (port 8000, device /dev/ttyACM0)
python -m honeywell_radio_exporter

# Or specify your USB device
python -m honeywell_radio_exporter --ramses-port /dev/ttyUSB0

# Custom port for Prometheus metrics
python -m honeywell_radio_exporter --ramses-port /dev/ttyUSB0 --port 9090

# With debug logging
python -m honeywell_radio_exporter --ramses-port /dev/ttyUSB0 --log-level DEBUG
```

### Without Virtual Environment

```bash
# Use venv's Python directly
./venv/bin/python -m honeywell_radio_exporter --ramses-port /dev/ttyUSB0

# Or install globally first
pip install -e .
honeywell-radio-exporter --ramses-port /dev/ttyUSB0
```

## Command Line Options

```
--port PORT              Prometheus HTTP server port (default: 8000)
--ramses-port DEVICE     RAMSES RF device port (default: /dev/ttyACM0)
--log-level LEVEL        Logging level: DEBUG, INFO, WARNING, ERROR (default: INFO)
```

## Environment Variables

- `RAMSES_RF_PATH`: Path to ramses_rf module (default: `/home/simon/src/3rd-party/ramses_rf/src`)
- `PYTHONUNBUFFERED`: Set to `1` for immediate log output

## Examples

### Example 1: Basic Run

```bash
cd /home/simon/src/development/honeywell-radio-exporter
source venv/bin/activate
python -m honeywell_radio_exporter --ramses-port /dev/ttyUSB0
```

### Example 2: Custom Port and Debug Logging

```bash
venv/bin/python -m honeywell_radio_exporter \
  --ramses-port /dev/ttyUSB0 \
  --port 9090 \
  --log-level DEBUG
```

### Example 3: With Environment Variable

```bash
export RAMSES_RF_PATH=/custom/path/to/ramses_rf/src
venv/bin/python -m honeywell_radio_exporter --ramses-port /dev/ttyUSB0
```

### Example 4: Test Mode (Prometheus Only, No Device)

```bash
# Run without ramses-port to test Prometheus server
# Note: This will start the metrics server but won't connect to hardware
venv/bin/python -m honeywell_radio_exporter --port 8000
# Then in another terminal:
curl http://localhost:8000/metrics
```

## Finding Your USB Device

```bash
# List USB devices
ls -l /dev/ttyUSB* /dev/ttyACM*

# Check device permissions
ls -l /dev/ttyUSB0

# If permission denied, add user to dialout group
sudo usermod -a -G dialout $USER
# Log out and back in for changes to take effect
```

## Verifying It's Working

1. **Check logs**: The exporter will log when it starts successfully
1. **Check metrics endpoint**:
   ```bash
   curl http://localhost:8000/metrics
   ```
1. **Check Prometheus metrics**: Look for metrics like:
   - `ramses_messages_total`
   - `ramses_message_types_total`
   - `ramses_active_devices`

## Running as a Service

See the `docs/ramses-prometheus-exporter.service` file for systemd service configuration.

```bash
# Install service
sudo cp docs/ramses-prometheus-exporter.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ramses-prometheus-exporter
sudo systemctl start ramses-prometheus-exporter

# Check status
sudo systemctl status ramses-prometheus-exporter

# View logs
sudo journalctl -u ramses-prometheus-exporter -f
```

## Running with Docker

See `README.docker.md` for detailed Docker instructions.

```bash
# Quick start with Docker Compose
docker-compose up -d

# Or manually
docker run -d \
  --name honeywell-radio-exporter \
  --device=/dev/ttyUSB0 \
  -v /home/simon/src/3rd-party/ramses_rf/src:/opt/ramses_rf/src:ro \
  -p 8000:8000 \
  honeywell-radio-exporter:latest \
  --ramses-port /dev/ttyUSB0
```

## Troubleshooting

### Issue: "Permission denied" on USB device

**Solution**: Add your user to the `dialout` group:

```bash
sudo usermod -a -G dialout $USER
# Then log out and back in
```

### Issue: "ramses_rf module not found"

**Solution**: Set the `RAMSES_RF_PATH` environment variable:

```bash
export RAMSES_RF_PATH=/path/to/ramses_rf/src
```

### Issue: Port already in use

**Solution**: Use a different port:

```bash
python -m honeywell_radio_exporter --port 9000
```

### Issue: Gateway configuration error

**Solution**: Check that your ramses_rf module version is compatible. You may need to update the
Gateway configuration in the code.

## Stopping the Exporter

- Press `Ctrl+C` if running in terminal
- If running as service: `sudo systemctl stop ramses-prometheus-exporter`
- If running in Docker: `docker stop honeywell-radio-exporter`
