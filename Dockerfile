# Multi-stage build for honeywell-radio-exporter
FROM python:3.11-slim as builder

# Set build arguments
ARG BUILD_DATE
ARG VCS_REF
ARG VERSION=1.0.0

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /build

# Copy requirements first for better caching
COPY requirements.txt pyproject.toml ./

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY honeywell_radio_exporter/ ./honeywell_radio_exporter/
COPY README.md ./

# Install the package
RUN pip install --no-cache-dir .

# Final stage - runtime image
FROM python:3.11-slim

# Metadata labels
LABEL maintainer="Simon <simon@example.com>" \
      org.opencontainers.image.title="honeywell-radio-exporter" \
      org.opencontainers.image.description="RAMSES RF Prometheus Exporter" \
      org.opencontainers.image.version="${VERSION:-1.0.0}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.revision="${VCS_REF}"

# Install runtime dependencies for USB/serial access
RUN apt-get update && apt-get install -y --no-install-recommends \
    udev \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -r exporter && \
    useradd -r -g exporter -u 1000 exporter && \
    mkdir -p /app /opt/ramses_rf && \
    chown -R exporter:exporter /app /opt/ramses_rf

# Set working directory
WORKDIR /app

# Copy installed package from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy project files
COPY --chown=exporter:exporter honeywell_radio_exporter/ ./honeywell_radio_exporter/
COPY --chown=exporter:exporter README.md ./

# Create directory for ramses_rf (will be mounted as volume at runtime)
RUN mkdir -p /opt/ramses_rf/src && \
    chown -R exporter:exporter /opt/ramses_rf

# Switch to non-root user
USER exporter

# Expose Prometheus metrics port
EXPOSE 8000

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    RAMSES_RF_PATH=/opt/ramses_rf/src \
    PORT=8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT}/metrics')" || exit 1

# Default command
ENTRYPOINT ["python", "-m", "honeywell_radio_exporter"]
CMD ["--port", "8000"]

