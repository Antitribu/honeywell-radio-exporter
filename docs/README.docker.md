# Docker Setup for Honeywell Radio Exporter

This document describes how to build and run the Honeywell Radio Exporter using Docker.

## Prerequisites

- Docker and Docker Compose installed
- Access to the RAMSES RF USB device (e.g., `/dev/ttyUSB0`)
- The `ramses_rf` module available (either included in image or mounted as volume)

## Building the Image

### Basic Build

```bash
docker build -t honeywell-radio-exporter:latest .
```

### Build with ramses_rf Module Included

If you want to include the `ramses_rf` module in the image:

```bash
# Option 1: Copy ramses_rf during build (requires it to be accessible)
docker build \
  --build-arg RAMSES_RF_PATH=/path/to/ramses_rf \
  -t honeywell-radio-exporter:latest \
  .
```

**Note:** The Dockerfile uses a multi-stage build. If the `ramses_rf` module is not available during
build, it can be mounted as a volume at runtime (see below).

## Running with Docker

### Basic Run

```bash
docker run -d \
  --name honeywell-radio-exporter \
  --device=/dev/ttyUSB0 \
  -v /home/simon/src/3rd-party/ramses_rf/src:/opt/ramses_rf/src:ro \
  -p 8000:8000 \
  honeywell-radio-exporter:latest \
  --ramses-port /dev/ttyUSB0 \
  --port 8000
```

### Using Docker Compose

The easiest way to run the exporter is using Docker Compose:

```bash
# Edit docker-compose.yml to adjust device path if needed
docker-compose up -d
```

View logs:

```bash
docker-compose logs -f
```

Stop the service:

```bash
docker-compose down
```

## Configuration

### Environment Variables

- `PORT`: Port for Prometheus metrics endpoint (default: 8000)
- `RAMSES_RF_PATH`: Path to ramses_rf module (default: /opt/ramses_rf/src)
- `PYTHONUNBUFFERED`: Set to 1 for immediate log output

### Command Line Arguments

The container accepts the same arguments as the standalone version:

```bash
--ramses-port DEVICE    # USB device path (e.g., /dev/ttyUSB0)
--port PORT            # Prometheus metrics port (default: 8000)
--log-level LEVEL      # Logging level (DEBUG, INFO, WARNING, ERROR)
```

### USB Device Access

The container needs access to the USB device. Make sure:

1. The device path is correct (check with `ls -l /dev/ttyUSB*`)
1. The device has proper permissions (you may need to add your user to the `dialout` group)
1. The device is passed to the container using `--device` flag or in docker-compose.yml

### Volume Mounts

If the `ramses_rf` module is not included in the image, mount it as a volume:

```bash
-v /path/to/ramses_rf/src:/opt/ramses_rf/src:ro
```

## Health Check

The container includes a health check that verifies the metrics endpoint is responding:

```bash
# Check health status
docker ps
# Look for "healthy" status

# Manual health check
curl http://localhost:8000/metrics
```

## Troubleshooting

### Device Permission Issues

If you get permission errors accessing the USB device:

```bash
# Add your user to dialout group (on host)
sudo usermod -a -G dialout $USER
# Log out and back in for changes to take effect

# Or run container with privileged mode (less secure)
docker run --privileged ...
```

### Module Not Found Errors

If you see errors about `ramses_rf` not being found:

1. Verify the volume mount path is correct
1. Check that the module exists at the mounted path
1. Ensure the path in `RAMSES_RF_PATH` environment variable matches the mount point

### Port Already in Use

If port 8000 is already in use:

```bash
# Use a different port
docker run -p 9000:8000 ...
# Or change the port mapping in docker-compose.yml
```

### Viewing Logs

```bash
# Docker
docker logs -f honeywell-radio-exporter

# Docker Compose
docker-compose logs -f
```

## Building for Production

For production deployments, consider:

1. Using specific version tags instead of `latest`
1. Setting resource limits in docker-compose.yml
1. Using a private registry
1. Implementing proper secrets management
1. Setting up monitoring and alerting

Example production build:

```bash
docker build \
  --build-arg VERSION=1.0.0 \
  --build-arg BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ') \
  --build-arg VCS_REF=$(git rev-parse --short HEAD) \
  -t registry.example.com/honeywell-radio-exporter:1.0.0 \
  .
```
