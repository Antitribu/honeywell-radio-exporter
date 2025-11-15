#!/usr/bin/env python3
"""
RAMSES RF Prometheus Exporter

This module listens to RAMSES RF messages and exposes metrics for Prometheus to scrape.
It tracks message types, device communications, and system state.
"""

import asyncio
import logging
import logging.handlers
import os
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Optional

# Add the ramses_rf module to the path
# Check environment variable first, then fall back to default path
ramses_rf_path = os.getenv("RAMSES_RF_PATH", "/home/simon/src/3rd-party/ramses_rf/src")
ramses_rf_path_obj = Path(ramses_rf_path)
if ramses_rf_path_obj.exists():
    sys.path.insert(0, str(ramses_rf_path_obj))
else:
    # Try the default path as fallback
    default_path = Path("/home/simon/src/3rd-party/ramses_rf/src")
    if default_path.exists():
        sys.path.insert(0, str(default_path))

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    Info,
    generate_latest,
    start_http_server,
    REGISTRY,
)

try:
    from ramses_rf import Gateway, Message, Code, I_, RP, RQ, W_
    from ramses_tx import Address, Command, Packet
    from ramses_tx.message import CODE_NAMES
    from ramses_tx.ramses import CODES_SCHEMA
except ImportError as e:
    print(f"Error importing ramses_rf: {e}")
    print("Make sure the ramses_rf module is available at /home/simon/src/3rd-party/ramses_rf")
    sys.exit(1)

# Configure logging
log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Set up root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# Console handler (if not already configured)
if not root_logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(log_format))
    root_logger.addHandler(console_handler)

# File handler for RAMSES messages log with rotation
log_file = "/tmp/ramses.log"
# Rotate when file reaches 10MB, keep 5 backup files
max_bytes = 10 * 1024 * 1024  # 10 MB
backup_count = 5
try:
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, mode="a", maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(log_format))
    root_logger.addHandler(file_handler)
    # Log to console that file logging is enabled
    temp_logger = logging.getLogger(__name__)
    temp_logger.info(
        f"Logging all messages to {log_file} "
        f"(rotation: {max_bytes // (1024*1024)}MB, {backup_count} backups)"
    )
except (OSError, PermissionError) as e:
    # If we can't write to the log file, log to console and continue
    print(f"Warning: Could not open log file {log_file}: {e}")
    print("Continuing without file logging...")

# Raw messages logger - for capturing raw message strings for testing
raw_messages_log = "/tmp/ramses.msgs"
raw_messages_logger = logging.getLogger("ramses.raw_messages")
raw_messages_logger.setLevel(logging.INFO)
raw_messages_logger.propagate = False  # Don't propagate to root logger

try:
    # Create file handler for raw messages - no rotation, just append
    raw_file_handler = logging.FileHandler(raw_messages_log, mode="a", encoding="utf-8")
    raw_file_handler.setLevel(logging.INFO)
    # Use a simple format - just the raw message string
    raw_file_handler.setFormatter(logging.Formatter("%(message)s"))
    raw_messages_logger.addHandler(raw_file_handler)
    # Log to console that raw message logging is enabled
    temp_logger = logging.getLogger(__name__)
    temp_logger.info(f"Logging raw messages to {raw_messages_log} for testing purposes")
except (OSError, PermissionError) as e:
    # If we can't write to the log file, log to console and continue
    print(f"Warning: Could not open raw messages log file {raw_messages_log}: {e}")
    print("Continuing without raw message logging...")

logger = logging.getLogger(__name__)


class RamsesPrometheusExporter:
    """Prometheus exporter for RAMSES RF messages."""

    def __init__(self, port: int = 8000, ramses_port: Optional[str] = None):
        self.port = port
        self.ramses_port = ramses_port
        self.gateway: Optional[Gateway] = None

        # Prometheus metrics
        self._setup_metrics()

        # Message tracking
        self.message_types = defaultdict(int)
        self.device_communications = defaultdict(int)
        self.last_message_time = time.time()

    def _setup_metrics(self):
        """Initialize Prometheus metrics."""

        # Message counters
        self.messages_total = Counter(
            "ramses_messages_total",
            "Total number of RAMSES messages received",
            ["message_type", "verb", "code", "source_device", "destination_device"],
        )

        self.message_types_counter = Counter(
            "ramses_message_types_total",
            "Total number of messages by type",
            ["code", "code_name", "verb"],
        )

        # Device communication counters
        self.device_communications_counter = Counter(
            "ramses_device_communications_total",
            "Total number of communications between devices",
            ["source_device", "destination_device", "verb"],
        )

        # System state gauges
        self.active_devices = Gauge(
            "ramses_active_devices", "Number of active devices in the system"
        )

        self.last_message_timestamp = Gauge(
            "ramses_last_message_timestamp", "Timestamp of the last message received"
        )

        self.message_rate = Gauge("ramses_message_rate", "Messages per second over the last minute")

        # Message processing metrics
        self.message_processing_duration = Histogram(
            "ramses_message_processing_duration_seconds",
            "Time spent processing messages",
            buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
        )

        # System information
        self.system_info = Info("ramses_system", "Information about the RAMSES RF system")

        # Error counters
        self.message_errors = Counter(
            "ramses_message_errors_total",
            "Total number of message processing errors",
            ["error_type"],
        )

        # Message payload size
        self.message_payload_size = Histogram(
            "ramses_message_payload_size_bytes",
            "Size of message payloads",
            buckets=[10, 50, 100, 200, 500, 1000, 2000],
        )

        # Device temperature gauge
        self.device_temperature = Gauge(
            "ramses_device_temperature_celsius",
            "Temperature reading per device in Celsius",
            ["device_id"],
        )

        # Device info metric - maps device_id to device_name
        self.device_info = Gauge(
            "ramses_device_info",
            "Device information mapping device ID to device name (always 1)",
            ["device_id", "device_name"],
        )

        # Zone info metric - maps zone_idx to zone_name
        self.zone_info = Gauge(
            "ramses_zone_info",
            "Zone information mapping zone index to zone name (always 1)",
            ["zone_idx", "zone_name"],
        )

        # Device last seen gauge
        self.device_last_seen = Gauge(
            "ramses_device_last_seen_timestamp",
            "Unix timestamp of the last message received from each device",
            ["device_id"],
        )

        # Device setpoint (target temperature) gauge
        self.device_setpoint = Gauge(
            "ramses_device_setpoint_celsius",
            "Target temperature setpoint per device or zone in Celsius",
            ["device_id", "zone_idx"],
        )

        # Zone window state gauge (0 = closed, 1 = open)
        self.zone_window_open = Gauge(
            "ramses_zone_window_open",
            "Window open state per zone (0 = closed, 1 = open)",
            ["device_id", "zone_idx"],
        )

        # Zone mode info gauge (always 1, mode as label)
        self.zone_mode = Gauge(
            "ramses_zone_mode_info",
            "Zone mode information (always 1, mode as label)",
            ["device_id", "zone_idx", "mode"],
        )

        # Zone/device heat demand gauge (0.0 to 1.0, representing 0-100%)
        self.heat_demand = Gauge(
            "ramses_heat_demand",
            "Heat demand per zone or system (0.0 to 1.0 representing 0-100%)",
            ["device_id", "zone_idx"],
        )

        # System sync gauge - seconds until next sync
        self.system_sync_remaining = Gauge(
            "ramses_system_sync_remaining_seconds",
            "Seconds remaining until next system sync cycle",
            ["device_id"],
        )

        # System sync last update timestamp
        self.system_sync_timestamp = Gauge(
            "ramses_system_sync_last_timestamp",
            "Unix timestamp of the last system sync message received",
            ["device_id"],
        )

        # Boiler communication metrics
        self.boiler_messages_sent = Counter(
            "ramses_boiler_messages_sent_total",
            "Total number of messages sent to boilers",
            ["boiler_id", "boiler_name", "message_code", "message_type"],
        )

        self.boiler_messages_received = Counter(
            "ramses_boiler_messages_received_total",
            "Total number of messages received from boilers",
            ["boiler_id", "boiler_name", "message_code", "message_type"],
        )

        self.boiler_last_seen = Gauge(
            "ramses_boiler_last_seen_timestamp",
            "Unix timestamp of the last message from this boiler",
            ["boiler_id", "boiler_name"],
        )

        self.boiler_last_contacted = Gauge(
            "ramses_boiler_last_contacted_timestamp",
            "Unix timestamp of the last message sent to this boiler",
            ["boiler_id", "boiler_name"],
        )

        # Boiler setpoint and modulation metrics
        self.boiler_setpoint = Gauge(
            "ramses_boiler_setpoint_celsius",
            "Current boiler setpoint temperature in Celsius",
            ["boiler_id", "boiler_name"],
        )

        self.boiler_modulation_level = Gauge(
            "ramses_boiler_modulation_level",
            "Current boiler modulation level (0.0 to 1.0 representing 0-100%)",
            ["boiler_id", "boiler_name"],
        )

        self.boiler_flame_active = Gauge(
            "ramses_boiler_flame_active",
            "Boiler flame status (0 = off, 1 = on)",
            ["boiler_id", "boiler_name"],
        )

        self.boiler_ch_active = Gauge(
            "ramses_boiler_ch_active",
            "Central heating active status (0 = off, 1 = on)",
            ["boiler_id", "boiler_name"],
        )

        self.boiler_dhw_active = Gauge(
            "ramses_boiler_dhw_active",
            "Domestic hot water active status (0 = off, 1 = on)",
            ["boiler_id", "boiler_name"],
        )

    async def start_gateway(self):
        """Start the RAMSES RF gateway."""
        try:
            logger.info(f"Starting RAMSES RF gateway on port: {self.ramses_port}")

            # Create gateway configuration
            # Note: config dict must be passed as 'config' parameter, not unpacked
            config = {
                "enable_eavesdrop": True,
                "reduce_processing": 0,  # Process all messages
            }

            self.gateway = Gateway(
                port_name=self.ramses_port, loop=asyncio.get_event_loop(), config=config
            )

            # Helper function to get device info (name/alias and type)
            def get_device_info(device_id: str) -> str:
                """Get device information including alias/name and type."""
                if not device_id or device_id == "unknown" or not self.gateway:
                    return device_id

                try:
                    # Try to get device from gateway
                    device = self.gateway.device_by_id.get(device_id)
                    if device:
                        # Get alias from traits
                        traits = device.traits if hasattr(device, "traits") else {}
                        alias = traits.get("alias") if isinstance(traits, dict) else None
                        device_type = getattr(device, "_SLUG", None) or getattr(
                            device, "type", None
                        )

                        # Build info string
                        info_parts = [device_id]
                        if alias:
                            info_parts.append(f"'{alias}'")
                        if device_type:
                            info_parts.append(f"({device_type})")

                        return " ".join(info_parts)
                except (AttributeError, KeyError, TypeError):
                    pass

                return device_id

            # Add a message handler to log and capture metrics for all messages
            def message_logger_and_metrics(msg: Message):
                """Log all messages and capture Prometheus metrics."""
                start_time = time.time()

                try:
                    # Log raw message string for testing purposes
                    raw_messages_logger.info(str(msg))

                    # Extract message details for logging
                    msg_code = str(msg.code) if msg.code else "unknown"
                    msg_code_name = self._get_code_name(msg.code)
                    msg_verb = str(msg.verb) if msg.verb else "unknown"
                    src_id = str(msg.src.id) if msg.src and hasattr(msg.src, "id") else "unknown"
                    dst_id = str(msg.dst.id) if msg.dst and hasattr(msg.dst, "id") else "unknown"

                    # Get device information with names/aliases
                    src_info = get_device_info(src_id)
                    dst_info = get_device_info(dst_id)

                    # Log the message with human-readable code name
                    payload_info = ""
                    if hasattr(msg, "payload") and msg.payload:
                        payload_info = f" | Payload: {msg.payload}"

                    # Include both code and human-readable name
                    code_display = (
                        f"{msg_code} ({msg_code_name})" if msg_code_name != msg_code else msg_code
                    )

                    logger.info(
                        f"Message: {code_display} {msg_verb} | "
                        f"From: {src_info} | To: {dst_info}"
                        f"{payload_info}"
                    )

                    # Capture metrics
                    self._capture_message_metrics(msg)

                    # Update processing duration
                    duration = time.time() - start_time
                    self.message_processing_duration.observe(duration)

                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    self.message_errors.labels(error_type=type(e).__name__).inc()

            # Add our handler to receive all messages (in addition to the default handler)
            self.gateway.add_msg_handler(message_logger_and_metrics)

            # Start the gateway
            await self.gateway.start()
            logger.info("RAMSES RF gateway started successfully")

        except Exception as e:
            logger.error(f"Failed to start RAMSES RF gateway: {e}")
            raise

    def _get_device_name(self, device_id: str) -> str:
        """Get device name/alias from gateway, return 'unknown' if not available."""
        if not device_id or device_id == "unknown" or not self.gateway:
            return "unknown"

        try:
            device = self.gateway.device_by_id.get(device_id)
            if device:
                traits = device.traits if hasattr(device, "traits") else {}
                alias = traits.get("alias") if isinstance(traits, dict) else None
                if alias:
                    return alias
        except (AttributeError, KeyError, TypeError):
            pass

        return "unknown"

    def _get_code_name(self, code: Any) -> str:
        """Get human-readable name for message code, return code as string if not available."""
        if not code:
            return "unknown"

        try:
            # CODE_NAMES uses Code enum objects as keys
            # Try direct lookup with the code object
            if code in CODE_NAMES:
                return CODE_NAMES[code]

            # Fallback: try to find in CODES_SCHEMA by matching code value
            code_str = str(code)
            for code_key, schema in CODES_SCHEMA.items():
                if str(code_key) == code_str:
                    name = schema.get("name")
                    if name:
                        return name
        except (AttributeError, KeyError, TypeError):
            pass

        # Fallback to code string representation
        return str(code)

    def _get_zone_name(self, zone_idx: str) -> str:
        """Get zone name from gateway zones, return 'unknown' if not available."""
        if not zone_idx or zone_idx == "unknown" or not self.gateway:
            return "unknown"

        try:
            # Access the TCS (controller) to get zones
            if hasattr(self.gateway, "_tcs") and self.gateway._tcs:
                tcs = self.gateway._tcs
                # Zones are accessed via the TCS
                if hasattr(tcs, "zones") and tcs.zones:
                    for zone in tcs.zones:
                        if zone.idx == zone_idx:
                            # Get the zone name if available
                            if hasattr(zone, "name") and zone.name:
                                return zone.name
        except (AttributeError, KeyError, TypeError):
            pass

        return "unknown"

    def _update_zone_info(self, zone_idx: str):
        """Update zone info metric with zone index and name mapping.

        Only creates/updates the metric if we have a real zone name (not 'unknown').
        This prevents cluttering metrics with unknown zones.
        """
        if not zone_idx or zone_idx == "unknown":
            return

        zone_name = self._get_zone_name(zone_idx)

        # Only set the metric if we have a real zone name (not 'unknown')
        # This prevents creating metrics for zones before their names are discovered
        if zone_name == "unknown":
            return

        # Set the zone info metric to 1 (it's always 1, used for joining)
        self.zone_info.labels(zone_idx=zone_idx, zone_name=zone_name).set(1)

    def _update_device_info(self, device_id: str):
        """Update device info metric with device ID and name mapping.

        Only creates/updates the metric if we have a real device name (not 'unknown').
        This prevents cluttering metrics with unknown devices.
        """
        if not device_id or device_id == "unknown":
            return

        device_name = self._get_device_name(device_id)

        # Only set the metric if we have a real device name (not 'unknown')
        # This prevents creating metrics for devices before their names are discovered
        if device_name == "unknown":
            return

        # Set the device info metric to 1 (it's always 1, used for joining)
        self.device_info.labels(device_id=device_id, device_name=device_name).set(1)

    def _capture_message_metrics(self, msg: Message):
        """Capture metrics from a RAMSES message."""

        # Extract message information
        msg_type = str(msg.code) if msg.code else "unknown"
        verb = str(msg.verb) if msg.verb else "unknown"
        code = str(msg.code) if msg.code else "unknown"

        # Get human-readable code name
        code_name = self._get_code_name(msg.code)

        source_device = str(msg.src.id) if msg.src and hasattr(msg.src, "id") else "unknown"
        dest_device = str(msg.dst.id) if msg.dst and hasattr(msg.dst, "id") else "unknown"

        # Update device info metrics for both source and destination
        self._update_device_info(source_device)
        self._update_device_info(dest_device)

        # Update device last seen timestamp for source device (message sender)
        if source_device != "unknown":
            self.device_last_seen.labels(device_id=source_device).set(time.time())

        # Update counters (without device names)
        self.messages_total.labels(
            message_type=msg_type,
            verb=verb,
            code=code,
            source_device=source_device,
            destination_device=dest_device,
        ).inc()

        self.message_types_counter.labels(code=code, code_name=code_name, verb=verb).inc()

        self.device_communications_counter.labels(
            source_device=source_device, destination_device=dest_device, verb=verb
        ).inc()

        # Update message type tracking
        self.message_types[f"{code}_{verb}"] += 1

        # Update device communication tracking
        self.device_communications[f"{source_device}_{dest_device}"] += 1

        # Track boiler-specific communications
        # Boilers are identified by device type 13: (BDR - electrical relay) or 10: (OTB - OpenTherm bridge)
        def is_boiler(device_id: str) -> bool:
            """Check if a device ID represents a boiler."""
            return device_id.startswith("13:") or device_id.startswith("10:")

        current_time = time.time()
        code_name = self._get_code_name(code)

        # Track messages FROM boilers
        if is_boiler(source_device):
            boiler_name = self._get_device_name(source_device)
            self.boiler_messages_received.labels(
                boiler_id=source_device,
                boiler_name=boiler_name,
                message_code=code,
                message_type=code_name,
            ).inc()
            self.boiler_last_seen.labels(boiler_id=source_device, boiler_name=boiler_name).set(
                current_time
            )

        # Track messages TO boilers
        if is_boiler(dest_device):
            boiler_name = self._get_device_name(dest_device)
            self.boiler_messages_sent.labels(
                boiler_id=dest_device,
                boiler_name=boiler_name,
                message_code=code,
                message_type=code_name,
            ).inc()
            self.boiler_last_contacted.labels(boiler_id=dest_device, boiler_name=boiler_name).set(
                current_time
            )

        # Update timestamp
        self.last_message_timestamp.set(time.time())
        self.last_message_time = time.time()

        # Update payload size if available
        if hasattr(msg, "payload") and msg.payload:
            payload_size = len(str(msg.payload))
            self.message_payload_size.observe(payload_size)

            # Capture zone names directly from zone_name messages (code 0004)
            # This allows us to learn zone names from the actual messages rather than
            # depending on pre-configured gateway TCS zones
            if (code == "0004" or code == "zone_name") and isinstance(msg.payload, dict):
                if "zone_idx" in msg.payload and "name" in msg.payload:
                    zone_idx = msg.payload["zone_idx"]
                    zone_name = msg.payload["name"]
                    if zone_idx and zone_name:
                        # Directly set the zone_info metric
                        self.zone_info.labels(zone_idx=zone_idx, zone_name=zone_name).set(1)
                        logger.debug(f"Captured zone name from message: {zone_idx} -> {zone_name}")

            # Extract temperature from payload if available
            if isinstance(msg.payload, dict) and "temperature" in msg.payload:
                try:
                    temperature = float(msg.payload["temperature"])
                    self.device_temperature.labels(device_id=source_device).set(temperature)
                    device_name = self._get_device_name(source_device)
                    logger.debug(
                        f"Updated temperature for device {source_device} ({device_name}): {temperature}°C"
                    )
                except (ValueError, TypeError) as e:
                    logger.warning(f"Could not parse temperature from payload: {e}")

            # Extract setpoint (target temperature) from payload if available
            # Setpoint appears in message codes 2309 (setpoint) and 2349 (zone_mode)
            if isinstance(msg.payload, dict) and "setpoint" in msg.payload:
                try:
                    setpoint = float(msg.payload["setpoint"])
                    # Get zone_idx if available, otherwise use '00'
                    zone_idx = msg.payload.get("zone_idx", "00")

                    # Update zone info if we have a zone_idx
                    if zone_idx and zone_idx != "00":
                        self._update_zone_info(zone_idx)

                    self.device_setpoint.labels(device_id=source_device, zone_idx=zone_idx).set(
                        setpoint
                    )
                    device_name = self._get_device_name(source_device)
                    logger.debug(
                        f"Updated setpoint for device {source_device} ({device_name}) zone {zone_idx}: {setpoint}°C"
                    )
                except (ValueError, TypeError) as e:
                    logger.warning(f"Could not parse setpoint from payload: {e}")

            # Extract window state from payload if available
            # Window state appears in message code 12B0 (window_state)
            if isinstance(msg.payload, dict) and "window_open" in msg.payload:
                try:
                    window_open = bool(msg.payload["window_open"])
                    zone_idx = msg.payload.get("zone_idx", "00")

                    # Update zone info if we have a zone_idx
                    if zone_idx and zone_idx != "00":
                        self._update_zone_info(zone_idx)

                    # Set to 1 if open, 0 if closed
                    self.zone_window_open.labels(device_id=source_device, zone_idx=zone_idx).set(
                        1 if window_open else 0
                    )
                    device_name = self._get_device_name(source_device)
                    status = "OPEN" if window_open else "CLOSED"
                    logger.debug(
                        f"Updated window state for device {source_device} ({device_name}) zone {zone_idx}: {status}"
                    )
                except (ValueError, TypeError) as e:
                    logger.warning(f"Could not parse window state from payload: {e}")

            # Extract zone mode from payload if available
            # Zone mode appears in message code 2349 (zone_mode)
            if isinstance(msg.payload, dict) and "mode" in msg.payload:
                try:
                    mode = str(msg.payload["mode"])
                    zone_idx = msg.payload.get("zone_idx", "00")

                    # Update zone info if we have a zone_idx
                    if zone_idx and zone_idx != "00":
                        self._update_zone_info(zone_idx)

                    # Clear previous mode metrics for this zone (set all to 0)
                    # This ensures only the current mode is set to 1
                    possible_modes = [
                        "follow_schedule",
                        "temporary_override",
                        "permanent_override",
                        "advanced_override",
                        "countdown",
                        "off",
                    ]
                    for m in possible_modes:
                        self.zone_mode.labels(
                            device_id=source_device, zone_idx=zone_idx, mode=m
                        ).set(0)

                    # Set current mode to 1
                    self.zone_mode.labels(
                        device_id=source_device, zone_idx=zone_idx, mode=mode
                    ).set(1)

                    device_name = self._get_device_name(source_device)
                    logger.debug(
                        f"Updated zone mode for device {source_device} ({device_name}) zone {zone_idx}: {mode}"
                    )
                except (ValueError, TypeError, KeyError) as e:
                    logger.warning(f"Could not parse zone mode from payload: {e}")

            # Extract heat demand from payload if available
            # Heat demand appears in message code 3150 (heat_demand)
            if isinstance(msg.payload, dict) and "heat_demand" in msg.payload:
                try:
                    heat_demand = float(msg.payload["heat_demand"])
                    # Heat demand can be zone-specific (zone_idx) or system-wide (domain_id)
                    # Use zone_idx if available, otherwise use domain_id, or '00' as fallback
                    zone_idx = msg.payload.get("zone_idx", msg.payload.get("domain_id", "00"))

                    # Update zone info if we have a zone_idx
                    if zone_idx and zone_idx != "00":
                        self._update_zone_info(zone_idx)

                    self.heat_demand.labels(device_id=source_device, zone_idx=zone_idx).set(
                        heat_demand
                    )

                    device_name = self._get_device_name(source_device)
                    percentage = heat_demand * 100
                    logger.debug(
                        f"Updated heat demand for device {source_device} ({device_name}) zone {zone_idx}: {percentage:.1f}%"
                    )
                except (ValueError, TypeError) as e:
                    logger.warning(f"Could not parse heat demand from payload: {e}")

            # Extract system sync information from payload if available
            # System sync appears in message code 1F09 (system_sync)
            if isinstance(msg.payload, dict) and "remaining_seconds" in msg.payload:
                try:
                    remaining_seconds = float(msg.payload["remaining_seconds"])

                    # Update the remaining seconds until next sync
                    self.system_sync_remaining.labels(device_id=source_device).set(
                        remaining_seconds
                    )

                    # Update the timestamp of when this sync message was received
                    self.system_sync_timestamp.labels(device_id=source_device).set(time.time())

                    device_name = self._get_device_name(source_device)
                    next_sync_time = msg.payload.get("_next_sync", "unknown")
                    logger.debug(
                        f"Updated system sync for device {source_device} ({device_name}): {remaining_seconds:.1f}s (next: {next_sync_time})"
                    )
                except (ValueError, TypeError) as e:
                    logger.warning(f"Could not parse system sync from payload: {e}")

            # Extract boiler setpoint from payload if available
            # Boiler setpoint appears in message code 22D9 (boiler_setpoint)
            if isinstance(msg.payload, dict) and "setpoint" in msg.payload and code == "22D9":
                try:
                    setpoint = float(msg.payload["setpoint"])
                    boiler_name = self._get_device_name(source_device)

                    # Update boiler setpoint metric
                    self.boiler_setpoint.labels(
                        boiler_id=source_device, boiler_name=boiler_name
                    ).set(setpoint)

                    logger.debug(
                        f"Updated boiler setpoint for {source_device} ({boiler_name}): {setpoint}°C"
                    )
                except (ValueError, TypeError) as e:
                    logger.warning(f"Could not parse boiler setpoint from payload: {e}")

            # Extract boiler modulation and status from payload if available
            # Boiler modulation and status appear in message codes 3EF0 and 3EF1 (actuator_state, actuator_cycle)
            if isinstance(msg.payload, dict) and code in ("3EF0", "3EF1"):
                try:
                    boiler_name = self._get_device_name(source_device)

                    # Modulation level (present in both 3EF0 and 3EF1)
                    if (
                        "modulation_level" in msg.payload
                        and msg.payload["modulation_level"] is not None
                    ):
                        modulation_level = float(msg.payload["modulation_level"])
                        self.boiler_modulation_level.labels(
                            boiler_id=source_device, boiler_name=boiler_name
                        ).set(modulation_level)
                        percentage = modulation_level * 100
                        logger.debug(
                            f"Updated boiler modulation for {source_device} ({boiler_name}): {percentage:.1f}%"
                        )

                    # Flame status (only in 3EF0)
                    if "flame_on" in msg.payload:
                        flame_on = bool(msg.payload["flame_on"])
                        self.boiler_flame_active.labels(
                            boiler_id=source_device, boiler_name=boiler_name
                        ).set(1 if flame_on else 0)
                        logger.debug(
                            f"Updated boiler flame status for {source_device} ({boiler_name}): {'ON' if flame_on else 'OFF'}"
                        )

                    # Central heating active status (only in 3EF0)
                    if "ch_active" in msg.payload:
                        ch_active = bool(msg.payload["ch_active"])
                        self.boiler_ch_active.labels(
                            boiler_id=source_device, boiler_name=boiler_name
                        ).set(1 if ch_active else 0)
                        logger.debug(
                            f"Updated boiler CH status for {source_device} ({boiler_name}): {'ACTIVE' if ch_active else 'INACTIVE'}"
                        )

                    # Domestic hot water active status (only in 3EF0)
                    if "dhw_active" in msg.payload:
                        dhw_active = bool(msg.payload["dhw_active"])
                        self.boiler_dhw_active.labels(
                            boiler_id=source_device, boiler_name=boiler_name
                        ).set(1 if dhw_active else 0)
                        logger.debug(
                            f"Updated boiler DHW status for {source_device} ({boiler_name}): {'ACTIVE' if dhw_active else 'INACTIVE'}"
                        )

                except (ValueError, TypeError, KeyError) as e:
                    logger.warning(f"Could not parse boiler modulation/status from payload: {e}")

        # Update active devices count
        if self.gateway and hasattr(self.gateway, "devices"):
            self.active_devices.set(len(self.gateway.devices))

        # Update system info
        self.system_info.info(
            {
                "gateway_version": getattr(self.gateway, "version", "unknown"),
                "total_devices": str(len(self.gateway.devices) if self.gateway else 0),
                "last_message_code": code,
                "last_message_verb": verb,
            }
        )

    def get_message_type_summary(self) -> Dict[str, int]:
        """Get a summary of message types seen."""
        return dict(self.message_types)

    def get_device_communication_summary(self) -> Dict[str, int]:
        """Get a summary of device communications."""
        return dict(self.device_communications)

    async def start_prometheus_server(self):
        """Start the Prometheus HTTP server."""
        try:
            start_http_server(self.port)
            logger.info(f"Prometheus HTTP server started on port {self.port}")
            logger.info(f"Metrics available at http://localhost:{self.port}/metrics")
        except Exception as e:
            logger.error(f"Failed to start Prometheus server: {e}")
            raise

    async def run(self):
        """Main run loop."""
        try:
            # Start Prometheus server
            await self.start_prometheus_server()

            # Start RAMSES gateway if port is specified
            if self.ramses_port:
                await self.start_gateway()

            # Keep the service running
            logger.info("RAMSES Prometheus exporter is running...")
            while True:
                await asyncio.sleep(1)

        except KeyboardInterrupt:
            logger.info("Shutting down...")
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
        finally:
            if self.gateway:
                await self.gateway.stop()


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="RAMSES RF Prometheus Exporter")
    parser.add_argument(
        "--port", type=int, default=8000, help="Prometheus HTTP server port (default: 8000)"
    )
    parser.add_argument(
        "--ramses-port",
        type=str,
        default="/dev/ttyACM0",
        help="RAMSES RF device port (e.g., /dev/ttyUSB0)",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)",
    )

    args = parser.parse_args()

    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    # Create and run exporter
    exporter = RamsesPrometheusExporter(port=args.port, ramses_port=args.ramses_port)

    try:
        asyncio.run(exporter.run())
    except KeyboardInterrupt:
        logger.info("Exporter stopped by user")
    except Exception as e:
        logger.error(f"Exporter failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
