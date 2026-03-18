# How to Run Honeywell Radio Exporter

Requires **`.mysql_creds`** (see README). Migrations run on startup.

## Quick Start

### Basic Usage (with RAMSES RF device)

```bash
source venv/bin/activate

python -m honeywell_radio_exporter
python -m honeywell_radio_exporter --ramses-port /dev/ttyUSB0 --port 9090
python -m honeywell_radio_exporter --ramses-port /dev/ttyUSB0 --log-level DEBUG

# HTTP + DB only (no USB watcher)
python -m honeywell_radio_exporter --no-device
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
--port PORT              HTTP port (default: 8000): /ui/, /metrics/, /api/devices
--host ADDR              Bind address (default: 0.0.0.0 = all interfaces, e.g. laptop on LAN).
                         Use `--host 127.0.0.1` for local-only.
--ramses-port DEVICE     RAMSES RF serial device (default: /dev/ttyACM0)
--gateway-type auto|hgi80|evofw3
                         HGI80 vs evofw3: **auto** uses USB VID / by-id path; plain ttyACM0
                         often cannot be told apart (ramses_rf warns, assumes evofw3). Set
                         **hgi80** for Honeywell HGI80 or **evofw3** for ESP32 firmware. With
                         CLI **auto**, env **`RAMSES_GATEWAY_TYPE=hgi80`** (or evofw3) applies.
--no-device              Do not start USB watcher (consumer still runs)
--log-level LEVEL        DEBUG, INFO, WARNING, ERROR (default: INFO)
```

Endpoints: **`/`** → **`/ui/`**; **`/api/devices`** JSON (`puzzle_log`, **`boiler_status`**: OpenTherm `10:` flame/CH/DHW/flow from live RAMSES); **`/api/messages/by_code?code=30C9&limit=25`**; **`/api/events`** SSE; **`/metrics/`** Prometheus.

## Environment Variables

- `LOG_ROTATE_ON_START`: If `1` (default), non-empty `logs/messages.log` is renamed to `.1` on startup (older `.N` shifted); set to `0` to append. Raw bus log `logs/raw_messages/raw_messages.log` is **not** rotated on start (only by size via RotatingFileHandler).
- `MYSQL_CREDS_PATH`: Override path to creds file
- `HTTP_BIND`: Default bind address (same as `--host`; default `0.0.0.0`)
- `RAMSES_GATEWAY_TYPE`: `hgi80` or `evofw3` when `--gateway-type auto` (see above).
- `RAMSES_RF_PATH`: Path to ramses_rf `src` (default: `/home/simon/src/3rd-party/ramses_rf/src`)
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
curl http://localhost:8000/metrics/
# UI: http://localhost:8000/ui/  |  JSON: curl http://localhost:8000/api/devices
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
1. **Device UI**: `http://localhost:8000/ui/` or `curl http://localhost:8000/api/devices`
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
