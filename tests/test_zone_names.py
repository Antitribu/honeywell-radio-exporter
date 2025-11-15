"""
Tests for zone name extraction and ramses_zone_info metric.

This module tests the functionality of extracting zone names from RAMSES RF
messages and populating the ramses_zone_info metric.
"""

import pytest
from unittest.mock import MagicMock, patch
from prometheus_client import REGISTRY

from honeywell_radio_exporter.ramses_prometheus_exporter import RamsesPrometheusExporter


@pytest.fixture(autouse=True)
def reset_prometheus_registry():
    """Reset the Prometheus registry before each test to avoid duplicate metric errors."""
    collectors = list(REGISTRY._collector_to_names.keys())
    for collector in collectors:
        try:
            REGISTRY.unregister(collector)
        except Exception:
            pass
    yield
    # Clean up after test
    collectors = list(REGISTRY._collector_to_names.keys())
    for collector in collectors:
        try:
            REGISTRY.unregister(collector)
        except Exception:
            pass


def test_zone_name_extraction():
    """Test that _get_zone_name correctly extracts zone names from gateway TCS."""
    with patch("honeywell_radio_exporter.ramses_prometheus_exporter.start_http_server"):
        exporter = RamsesPrometheusExporter(port=8000, ramses_port="/dev/ttyUSB0")

        # Mock the gateway with TCS and zones
        mock_gateway = MagicMock()
        mock_tcs = MagicMock()

        # Create mock zones with names
        mock_zone1 = MagicMock()
        mock_zone1.idx = "01"
        mock_zone1.name = "Living Room"

        mock_zone2 = MagicMock()
        mock_zone2.idx = "02"
        mock_zone2.name = "Bedroom"

        mock_zone3 = MagicMock()
        mock_zone3.idx = "03"
        mock_zone3.name = None  # Zone without a name

        mock_tcs.zones = [mock_zone1, mock_zone2, mock_zone3]
        mock_gateway._tcs = mock_tcs
        exporter.gateway = mock_gateway

        # Test zone with name
        assert exporter._get_zone_name("01") == "Living Room"
        assert exporter._get_zone_name("02") == "Bedroom"

        # Test zone without name
        assert exporter._get_zone_name("03") == "unknown"

        # Test non-existent zone
        assert exporter._get_zone_name("99") == "unknown"


def test_zone_info_metric_structure():
    """Test that ramses_zone_info metric has the correct structure and labels."""
    with patch("honeywell_radio_exporter.ramses_prometheus_exporter.start_http_server"):
        exporter = RamsesPrometheusExporter(port=8000, ramses_port="/dev/ttyUSB0")

        # Mock gateway with zones
        mock_gateway = MagicMock()
        mock_tcs = MagicMock()
        mock_zone = MagicMock()
        mock_zone.idx = "01"
        mock_zone.name = "Kitchen"
        mock_tcs.zones = [mock_zone]
        mock_gateway._tcs = mock_tcs
        exporter.gateway = mock_gateway

        # Update zone info
        exporter._update_zone_info("01")

        # Verify the metric exists and has correct labels
        metric_family = REGISTRY.get_sample_value(
            "ramses_zone_info", {"zone_idx": "01", "zone_name": "Kitchen"}
        )
        assert metric_family == 1.0


def test_zone_info_metric_labels():
    """Test that ramses_zone_info metric has zone_idx and zone_name labels."""
    with patch("honeywell_radio_exporter.ramses_prometheus_exporter.start_http_server"):
        exporter = RamsesPrometheusExporter(port=8000, ramses_port="/dev/ttyUSB0")

        # Mock gateway with multiple zones
        mock_gateway = MagicMock()
        mock_tcs = MagicMock()

        zones = []
        for idx, name in [("01", "Living Room"), ("02", "Bedroom"), ("03", "Kitchen")]:
            mock_zone = MagicMock()
            mock_zone.idx = idx
            mock_zone.name = name
            zones.append(mock_zone)

        mock_tcs.zones = zones
        mock_gateway._tcs = mock_tcs
        exporter.gateway = mock_gateway

        # Update all zones
        for idx in ["01", "02", "03"]:
            exporter._update_zone_info(idx)

        # Check that all zones are present with correct labels
        assert (
            REGISTRY.get_sample_value(
                "ramses_zone_info", {"zone_idx": "01", "zone_name": "Living Room"}
            )
            == 1.0
        )
        assert (
            REGISTRY.get_sample_value(
                "ramses_zone_info", {"zone_idx": "02", "zone_name": "Bedroom"}
            )
            == 1.0
        )
        assert (
            REGISTRY.get_sample_value(
                "ramses_zone_info", {"zone_idx": "03", "zone_name": "Kitchen"}
            )
            == 1.0
        )


def test_zone_info_metric_unknown_zone():
    """Test that ramses_zone_info metric is NOT created for zones with 'unknown' names."""
    with patch("honeywell_radio_exporter.ramses_prometheus_exporter.start_http_server"):
        exporter = RamsesPrometheusExporter(port=8000, ramses_port="/dev/ttyUSB0")

        # Mock gateway with a zone that has no name
        mock_gateway = MagicMock()
        mock_tcs = MagicMock()
        mock_zone = MagicMock()
        mock_zone.idx = "01"
        mock_zone.name = None  # Zone without name
        mock_tcs.zones = [mock_zone]
        mock_gateway._tcs = mock_tcs
        exporter.gateway = mock_gateway

        # Try to update zone info for unknown zone
        exporter._update_zone_info("01")

        # Verify the metric was NOT created
        metric_value = REGISTRY.get_sample_value(
            "ramses_zone_info", {"zone_idx": "01", "zone_name": "unknown"}
        )
        assert metric_value is None


def test_zone_info_not_created_for_invalid_zone_idx():
    """Test that ramses_zone_info metric is NOT created for invalid zone indices."""
    with patch("honeywell_radio_exporter.ramses_prometheus_exporter.start_http_server"):
        exporter = RamsesPrometheusExporter(port=8000, ramses_port="/dev/ttyUSB0")

        # Mock gateway
        mock_gateway = MagicMock()
        mock_tcs = MagicMock()
        mock_tcs.zones = []
        mock_gateway._tcs = mock_tcs
        exporter.gateway = mock_gateway

        # Try to update with invalid zone indices
        exporter._update_zone_info("")
        exporter._update_zone_info("unknown")
        exporter._update_zone_info(None)

        # Verify no metrics were created
        from prometheus_client import generate_latest

        output = generate_latest(REGISTRY).decode("utf-8")
        assert "ramses_zone_info" not in output or 'zone_name="unknown"' not in output


def test_message_processing_updates_zone_info():
    """Test that processing zone-specific messages updates zone info."""
    with patch("honeywell_radio_exporter.ramses_prometheus_exporter.start_http_server"):
        exporter = RamsesPrometheusExporter(port=8000, ramses_port="/dev/ttyUSB0")

        # Mock gateway with zone
        mock_gateway = MagicMock()
        mock_tcs = MagicMock()
        mock_zone = MagicMock()
        mock_zone.idx = "01"
        mock_zone.name = "Living Room"
        mock_tcs.zones = [mock_zone]
        mock_gateway._tcs = mock_tcs
        exporter.gateway = mock_gateway

        # Create a mock message with zone_idx in payload
        mock_msg = MagicMock()
        mock_msg.code = "2309"
        mock_msg.verb = "I"
        mock_msg.src = MagicMock()
        mock_msg.src.id = "01:123456"
        mock_msg.dst = MagicMock()
        mock_msg.dst.id = "--:------"
        mock_msg.payload = {"setpoint": 20.5, "zone_idx": "01"}

        # Process the message
        exporter._capture_message_metrics(mock_msg)

        # Verify zone info was updated
        metric_value = REGISTRY.get_sample_value(
            "ramses_zone_info", {"zone_idx": "01", "zone_name": "Living Room"}
        )
        assert metric_value == 1.0


def test_zone_info_metric_export_format():
    """Test that zone info metric exports in correct Prometheus format."""
    with patch("honeywell_radio_exporter.ramses_prometheus_exporter.start_http_server"):
        exporter = RamsesPrometheusExporter(port=8000, ramses_port="/dev/ttyUSB0")

        # Mock gateway with zones
        mock_gateway = MagicMock()
        mock_tcs = MagicMock()
        mock_zone = MagicMock()
        mock_zone.idx = "01"
        mock_zone.name = "Master Bedroom"
        mock_tcs.zones = [mock_zone]
        mock_gateway._tcs = mock_tcs
        exporter.gateway = mock_gateway

        # Update zone info
        exporter._update_zone_info("01")

        # Export metrics
        from prometheus_client import generate_latest

        output = generate_latest(REGISTRY).decode("utf-8")

        # Check that the metric is in the output with correct format
        assert "ramses_zone_info" in output
        assert 'zone_idx="01"' in output
        assert 'zone_name="Master Bedroom"' in output
        assert "ramses_zone_info{zone_idx=" in output


def test_zone_name_updates_for_multiple_message_types():
    """Test that zone info is updated for various message types that include zone_idx."""
    with patch("honeywell_radio_exporter.ramses_prometheus_exporter.start_http_server"):
        exporter = RamsesPrometheusExporter(port=8000, ramses_port="/dev/ttyUSB0")

        # Mock gateway with zone
        mock_gateway = MagicMock()
        mock_tcs = MagicMock()
        mock_zone = MagicMock()
        mock_zone.idx = "02"
        mock_zone.name = "Office"
        mock_tcs.zones = [mock_zone]
        mock_gateway._tcs = mock_tcs
        exporter.gateway = mock_gateway

        # Test different message types
        message_types = [
            ("2309", {"setpoint": 21.0, "zone_idx": "02"}),  # Setpoint
            ("12B0", {"window_open": False, "zone_idx": "02"}),  # Window state
            ("2349", {"mode": "follow_schedule", "zone_idx": "02"}),  # Zone mode
            ("3150", {"heat_demand": 0.5, "zone_idx": "02"}),  # Heat demand
        ]

        for code, payload in message_types:
            mock_msg = MagicMock()
            mock_msg.code = code
            mock_msg.verb = "I"
            mock_msg.src = MagicMock()
            mock_msg.src.id = "01:123456"
            mock_msg.dst = MagicMock()
            mock_msg.dst.id = "--:------"
            mock_msg.payload = payload

            # Process message
            exporter._capture_message_metrics(mock_msg)

        # Verify zone info was created
        metric_value = REGISTRY.get_sample_value(
            "ramses_zone_info", {"zone_idx": "02", "zone_name": "Office"}
        )
        assert metric_value == 1.0


def test_zone_info_ignores_zone_idx_00():
    """Test that zone_idx='00' does not create a zone_info metric."""
    with patch("honeywell_radio_exporter.ramses_prometheus_exporter.start_http_server"):
        exporter = RamsesPrometheusExporter(port=8000, ramses_port="/dev/ttyUSB0")

        # Mock gateway
        mock_gateway = MagicMock()
        mock_tcs = MagicMock()
        mock_tcs.zones = []
        mock_gateway._tcs = mock_tcs
        exporter.gateway = mock_gateway

        # Create message with zone_idx='00'
        mock_msg = MagicMock()
        mock_msg.code = "2309"
        mock_msg.verb = "I"
        mock_msg.src = MagicMock()
        mock_msg.src.id = "01:123456"
        mock_msg.dst = MagicMock()
        mock_msg.dst.id = "--:------"
        mock_msg.payload = {"setpoint": 20.0, "zone_idx": "00"}

        # Process message
        exporter._capture_message_metrics(mock_msg)

        # Verify no zone_info metric was created for zone_idx="00"
        from prometheus_client import generate_latest

        output = generate_latest(REGISTRY).decode("utf-8")

        # Extract only the ramses_zone_info section
        lines = output.split("\n")
        zone_info_lines = []
        in_zone_info = False
        for line in lines:
            if "ramses_zone_info" in line:
                in_zone_info = True
            elif in_zone_info and line.startswith("# "):
                break  # Next metric started
            if in_zone_info:
                zone_info_lines.append(line)

        zone_info_output = "\n".join(zone_info_lines)

        # Should not have zone_info for zone_idx="00" in the zone_info metric
        # (zone_idx="00" may appear in other metrics like device_setpoint, which is fine)
        assert (
            "ramses_zone_info{" not in zone_info_output or 'zone_idx="00"' not in zone_info_output
        )


def test_zone_name_caching():
    """Test that zone names are retrieved efficiently and cached behavior."""
    with patch("honeywell_radio_exporter.ramses_prometheus_exporter.start_http_server"):
        exporter = RamsesPrometheusExporter(port=8000, ramses_port="/dev/ttyUSB0")

        # Mock gateway with zone
        mock_gateway = MagicMock()
        mock_tcs = MagicMock()
        mock_zone = MagicMock()
        mock_zone.idx = "01"
        mock_zone.name = "Dining Room"
        mock_tcs.zones = [mock_zone]
        mock_gateway._tcs = mock_tcs
        exporter.gateway = mock_gateway

        # Call _get_zone_name multiple times
        name1 = exporter._get_zone_name("01")
        name2 = exporter._get_zone_name("01")
        name3 = exporter._get_zone_name("01")

        # All should return the same name
        assert name1 == "Dining Room"
        assert name2 == "Dining Room"
        assert name3 == "Dining Room"

        # Update zone info multiple times
        exporter._update_zone_info("01")
        exporter._update_zone_info("01")
        exporter._update_zone_info("01")

        # Metric should still be 1.0
        metric_value = REGISTRY.get_sample_value(
            "ramses_zone_info", {"zone_idx": "01", "zone_name": "Dining Room"}
        )
        assert metric_value == 1.0
