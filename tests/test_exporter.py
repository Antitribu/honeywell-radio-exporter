#!/usr/bin/env python3
"""
Tests for the RAMSES RF Prometheus Exporter

This module contains unit tests for the exporter functionality.
"""

import asyncio
import sys
import time
from unittest.mock import Mock, MagicMock, patch

import pytest

# Add the ramses_rf module to the path
sys.path.insert(0, "/home/simon/src/3rd-party/ramses_rf/src")

# Import the exporter
from honeywell_radio_exporter.ramses_prometheus_exporter import RamsesPrometheusExporter


class MockMessage:
    """Mock RAMSES message for testing."""

    def __init__(self, code="0001", verb="I", src_id="01:123456", dst_id="02:654321", payload=None):
        self.code = code
        self.verb = verb
        self.src = Mock()
        self.src.id = src_id
        self.dst = Mock()
        self.dst.id = dst_id
        self.payload = payload or {"test": "data"}
        self._pkt = Mock()
        self._pkt._ctx = "test_context"


class MockGateway:
    """Mock RAMSES gateway for testing."""

    def __init__(self):
        self.devices = [Mock(), Mock(), Mock()]  # 3 mock devices
        self.version = "1.0.0"
        self._msg_handler = None

    async def start(self):
        pass

    async def stop(self):
        pass


class TestRamsesPrometheusExporter:
    """Test cases for RamsesPrometheusExporter class."""

    def test_exporter_initialization(self):
        """Test that the exporter initializes correctly."""
        exporter = RamsesPrometheusExporter(port=8000)

        assert exporter.port == 8000
        assert exporter.ramses_port is None
        assert exporter.gateway is None
        assert hasattr(exporter, "messages_total")
        assert hasattr(exporter, "message_types_counter")
        assert hasattr(exporter, "device_communications_counter")
        assert hasattr(exporter, "active_devices")
        assert hasattr(exporter, "last_message_timestamp")
        assert hasattr(exporter, "message_rate")
        assert hasattr(exporter, "message_processing_duration")
        assert hasattr(exporter, "system_info")
        assert hasattr(exporter, "message_errors")
        assert hasattr(exporter, "message_payload_size")

    def test_exporter_with_ramses_port(self):
        """Test that the exporter initializes with RAMSES port."""
        exporter = RamsesPrometheusExporter(port=8000, ramses_port="/dev/ttyUSB0")

        assert exporter.port == 8000
        assert exporter.ramses_port == "/dev/ttyUSB0"

    def test_capture_message_metrics(self):
        """Test that message metrics are captured correctly."""
        exporter = RamsesPrometheusExporter()

        # Create a mock message
        msg = MockMessage("0001", "I", "01:123456", "02:654321", {"temperature": 20.5})

        # Capture metrics
        exporter._capture_message_metrics(msg)

        # Check that metrics were updated
        assert exporter.message_types["0001_I"] == 1
        assert exporter.device_communications["01:123456_02:654321"] == 1
        assert exporter.last_message_time > 0

    def test_capture_multiple_messages(self):
        """Test that multiple messages are captured correctly."""
        exporter = RamsesPrometheusExporter()

        # Create multiple messages
        messages = [
            MockMessage("0001", "I", "01:123456", "02:654321"),
            MockMessage("0002", "RP", "02:654321", "01:123456"),
            MockMessage("0001", "I", "01:123456", "02:654321"),  # Duplicate
        ]

        # Capture metrics for all messages
        for msg in messages:
            exporter._capture_message_metrics(msg)

        # Check that metrics were updated correctly
        assert exporter.message_types["0001_I"] == 2  # Two messages with same type
        assert exporter.message_types["0002_RP"] == 1  # One message with this type
        assert exporter.device_communications["01:123456_02:654321"] == 2
        assert exporter.device_communications["02:654321_01:123456"] == 1

    def test_get_message_type_summary(self):
        """Test that message type summary is returned correctly."""
        exporter = RamsesPrometheusExporter()

        # Add some test data
        exporter.message_types["0001_I"] = 5
        exporter.message_types["0002_RP"] = 3

        summary = exporter.get_message_type_summary()

        assert summary["0001_I"] == 5
        assert summary["0002_RP"] == 3
        assert len(summary) == 2

    def test_get_device_communication_summary(self):
        """Test that device communication summary is returned correctly."""
        exporter = RamsesPrometheusExporter()

        # Add some test data
        exporter.device_communications["01:123456_02:654321"] = 10
        exporter.device_communications["02:654321_03:789012"] = 5

        summary = exporter.get_device_communication_summary()

        assert summary["01:123456_02:654321"] == 10
        assert summary["02:654321_03:789012"] == 5
        assert len(summary) == 2

    def test_capture_message_metrics_with_gateway(self):
        """Test that metrics are captured correctly when gateway is available."""
        exporter = RamsesPrometheusExporter()
        mock_gateway = MockGateway()
        exporter.gateway = mock_gateway

        msg = MockMessage("0001", "I", "01:123456", "02:654321")
        exporter._capture_message_metrics(msg)

        # Check that active devices count was updated
        assert exporter.active_devices._value.get() == 3  # 3 mock devices

    def test_capture_message_metrics_with_payload(self):
        """Test that payload size is captured correctly."""
        exporter = RamsesPrometheusExporter()

        # Create message with payload
        payload = {"temperature": 20.5, "humidity": 60, "status": "ok"}
        msg = MockMessage("0001", "I", "01:123456", "02:654321", payload)

        exporter._capture_message_metrics(msg)

        # Check that payload size was captured (approximate)
        # The exact size depends on string representation
        assert exporter.message_payload_size._sum.get() > 0

    @pytest.mark.asyncio
    async def test_start_prometheus_server(self):
        """Test that Prometheus server starts correctly."""
        exporter = RamsesPrometheusExporter(port=8002)

        # Mock the start_http_server function
        with patch(
            "honeywell_radio_exporter.ramses_prometheus_exporter.start_http_server"
        ) as mock_start:
            await exporter.start_prometheus_server()
            mock_start.assert_called_once_with(8002)

    @pytest.mark.asyncio
    async def test_start_prometheus_server_error(self):
        """Test that errors in starting Prometheus server are handled."""
        exporter = RamsesPrometheusExporter(port=8003)

        # Mock the start_http_server function to raise an exception
        with patch(
            "honeywell_radio_exporter.ramses_prometheus_exporter.start_http_server"
        ) as mock_start:
            mock_start.side_effect = Exception("Server error")

            with pytest.raises(Exception, match="Server error"):
                await exporter.start_prometheus_server()


@pytest.mark.asyncio
async def test_exporter_integration():
    """Integration test for the exporter."""
    exporter = RamsesPrometheusExporter(port=8004)

    # Test that we can create an exporter and capture some metrics
    assert exporter is not None

    # Test message processing
    messages = [
        MockMessage("0001", "I", "01:123456", "02:654321"),
        MockMessage("0002", "RP", "02:654321", "01:123456"),
        MockMessage("0003", "RQ", "01:123456", "03:789012"),
    ]

    for msg in messages:
        exporter._capture_message_metrics(msg)

    # Verify metrics were captured
    summary = exporter.get_message_type_summary()
    assert len(summary) == 3
    assert summary["0001_I"] == 1
    assert summary["0002_RP"] == 1
    assert summary["0003_RQ"] == 1


def test_metrics_creation():
    """Test that all expected metrics are created."""
    exporter = RamsesPrometheusExporter()

    expected_metrics = [
        "messages_total",
        "message_types_counter",
        "device_communications_counter",
        "active_devices",
        "last_message_timestamp",
        "message_rate",
        "message_processing_duration",
        "system_info",
        "message_errors",
        "message_payload_size",
    ]

    for metric_name in expected_metrics:
        assert hasattr(exporter, metric_name), f"Metric '{metric_name}' missing"


if __name__ == "__main__":
    pytest.main([__file__])
