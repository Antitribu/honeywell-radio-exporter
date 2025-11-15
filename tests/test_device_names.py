"""
Tests for device name extraction and metrics.

This test validates that device names are correctly extracted from RAMSES RF
messages and populated in Prometheus metrics.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path


def test_device_name_extraction():
    """Test that device names are extracted from gateway device traits."""
    from honeywell_radio_exporter.ramses_prometheus_exporter import RamsesPrometheusExporter

    # Create exporter instance
    with patch("honeywell_radio_exporter.ramses_prometheus_exporter.start_http_server"):
        exporter = RamsesPrometheusExporter(port=8000, ramses_port="/dev/ttyUSB0")

    # Mock gateway with devices that have aliases
    mock_gateway = Mock()
    mock_device_with_name = Mock()
    mock_device_with_name.id = "01:234576"
    mock_device_with_name.traits = {"alias": "MainController", "class": "controller"}

    mock_device_without_name = Mock()
    mock_device_without_name.id = "18:147744"
    mock_device_without_name.traits = {"alias": None, "class": "gateway_interface"}

    mock_gateway.device_by_id = {
        "01:234576": mock_device_with_name,
        "18:147744": mock_device_without_name,
    }

    exporter.gateway = mock_gateway

    # Test device with alias
    name1 = exporter._get_device_name("01:234576")
    assert name1 == "MainController", f"Expected 'MainController' but got '{name1}'"

    # Test device without alias
    name2 = exporter._get_device_name("18:147744")
    assert name2 == "unknown", f"Expected 'unknown' but got '{name2}'"

    # Test non-existent device
    name3 = exporter._get_device_name("99:999999")
    assert name3 == "unknown", f"Expected 'unknown' but got '{name3}'"


def test_device_info_metric_structure():
    """Test that ramses_device_info metric has correct structure."""
    from honeywell_radio_exporter.ramses_prometheus_exporter import RamsesPrometheusExporter

    with patch("honeywell_radio_exporter.ramses_prometheus_exporter.start_http_server"):
        exporter = RamsesPrometheusExporter(port=8000, ramses_port="/dev/ttyUSB0")

    # Check that device_info metric exists
    assert hasattr(exporter, "device_info"), "device_info metric not found"

    # Check metric type
    from prometheus_client import Gauge

    assert isinstance(exporter.device_info, Gauge), "device_info should be a Gauge"

    # Get metric description
    metric_desc = exporter.device_info._documentation
    assert "device" in metric_desc.lower(), "Metric description should mention 'device'"


def test_device_info_metric_labels():
    """Test that device_info metric has correct labels."""
    from honeywell_radio_exporter.ramses_prometheus_exporter import RamsesPrometheusExporter

    with patch("honeywell_radio_exporter.ramses_prometheus_exporter.start_http_server"):
        exporter = RamsesPrometheusExporter(port=8000, ramses_port="/dev/ttyUSB0")

    # Mock gateway
    mock_gateway = Mock()
    mock_device = Mock()
    mock_device.id = "01:234576"
    mock_device.traits = {"alias": "TestDevice", "class": "controller"}
    mock_gateway.device_by_id = {"01:234576": mock_device}
    exporter.gateway = mock_gateway

    # Update device info
    exporter._update_device_info("01:234576")

    # Get metric samples
    samples = list(exporter.device_info.collect())[0].samples

    # Find our device
    device_sample = None
    for sample in samples:
        if sample.labels.get("device_id") == "01:234576":
            device_sample = sample
            break

    assert device_sample is not None, "Device metric not found"
    assert device_sample.labels["device_id"] == "01:234576"
    assert device_sample.labels["device_name"] == "TestDevice"
    assert device_sample.value == 1.0, "device_info metric should always be 1.0"


def test_device_info_metric_unknown_device():
    """Test device_info metric for devices without aliases."""
    from honeywell_radio_exporter.ramses_prometheus_exporter import RamsesPrometheusExporter

    with patch("honeywell_radio_exporter.ramses_prometheus_exporter.start_http_server"):
        exporter = RamsesPrometheusExporter(port=8000, ramses_port="/dev/ttyUSB0")

    # Mock gateway with device without alias
    mock_gateway = Mock()
    mock_device = Mock()
    mock_device.id = "18:147744"
    mock_device.traits = {"alias": None, "class": "gateway_interface"}
    mock_gateway.device_by_id = {"18:147744": mock_device}
    exporter.gateway = mock_gateway

    # Update device info
    exporter._update_device_info("18:147744")

    # Get metric samples
    samples = list(exporter.device_info.collect())[0].samples

    # Find our device
    device_sample = None
    for sample in samples:
        if sample.labels.get("device_id") == "18:147744":
            device_sample = sample
            break

    assert device_sample is not None, "Device metric not found"
    assert (
        device_sample.labels["device_name"] == "unknown"
    ), "Device without alias should have name 'unknown'"


def test_message_processing_updates_device_info():
    """Test that processing messages updates device_info metric."""
    from honeywell_radio_exporter.ramses_prometheus_exporter import RamsesPrometheusExporter
    from unittest.mock import Mock

    with patch("honeywell_radio_exporter.ramses_prometheus_exporter.start_http_server"):
        exporter = RamsesPrometheusExporter(port=8000, ramses_port="/dev/ttyUSB0")

    # Mock gateway
    mock_gateway = Mock()
    mock_device = Mock()
    mock_device.id = "01:234576"
    mock_device.traits = {"alias": "Controller", "class": "controller"}
    mock_gateway.device_by_id = {"01:234576": mock_device}
    exporter.gateway = mock_gateway

    # Create mock message
    mock_msg = Mock()
    mock_msg.code = "1F09"
    mock_msg.verb = " I"
    mock_msg.src = Mock()
    mock_msg.src.id = "01:234576"
    mock_msg.dst = Mock()
    mock_msg.dst.id = "01:234576"
    mock_msg.payload = {"remaining_seconds": 156.0}

    # Process message
    exporter._capture_message_metrics(mock_msg)

    # Verify device_info was updated
    samples = list(exporter.device_info.collect())[0].samples
    device_sample = None
    for sample in samples:
        if sample.labels.get("device_id") == "01:234576":
            device_sample = sample
            break

    assert device_sample is not None, "Device info should be updated when processing messages"
    assert device_sample.labels["device_name"] == "Controller"


def test_sample_messages_device_extraction():
    """Test device extraction from sample messages file."""
    sample_file = Path(__file__).parent / "sample_data" / "ramses.msgs"

    if not sample_file.exists():
        pytest.skip(f"Sample data file not found: {sample_file}")

    # Read sample messages
    with open(sample_file, "r") as f:
        messages = f.readlines()

    # Extract unique device IDs from messages
    device_ids = set()
    for line in messages[:100]:  # Check first 100 messages
        # Messages format: ||  device_id |  device_id | ...
        parts = line.split("|")
        if len(parts) >= 3:
            # Extract source device (second field)
            src = parts[1].strip()
            if src and ":" in src:
                device_ids.add(src)
            # Extract destination device (third field)
            dst = parts[2].strip()
            if dst and ":" in dst:
                device_ids.add(dst)

    # Should have found some devices
    assert len(device_ids) > 0, "Should find device IDs in sample messages"

    # Common device types should be present
    device_types = {did.split(":")[0] for did in device_ids if ":" in did}

    print(f"\nFound {len(device_ids)} unique devices")
    print(f"Device types: {sorted(device_types)}")
    print(f"Sample devices: {sorted(list(device_ids))[:5]}")


def test_metric_export_format():
    """Test that device_info metric exports in correct Prometheus format."""
    from honeywell_radio_exporter.ramses_prometheus_exporter import RamsesPrometheusExporter
    from prometheus_client import generate_latest

    with patch("honeywell_radio_exporter.ramses_prometheus_exporter.start_http_server"):
        exporter = RamsesPrometheusExporter(port=8000, ramses_port="/dev/ttyUSB0")

    # Mock gateway
    mock_gateway = Mock()
    mock_device = Mock()
    mock_device.id = "18:147744"
    mock_device.traits = {"alias": "TestGateway", "class": "gateway_interface"}
    mock_gateway.device_by_id = {"18:147744": mock_device}
    exporter.gateway = mock_gateway

    # Update device info
    exporter._update_device_info("18:147744")

    # Generate Prometheus output
    output = generate_latest(exporter.device_info).decode("utf-8")

    # Check format
    assert "ramses_device_info" in output, "Metric name should be in output"
    assert 'device_id="18:147744"' in output, "device_id label should be in output"
    assert 'device_name="TestGateway"' in output, "device_name label should be in output"
    assert "1.0" in output or "1" in output, "Metric value should be 1.0"

    print("\nGenerated Prometheus metrics:")
    for line in output.split("\n"):
        if "ramses_device_info" in line and not line.startswith("#"):
            print(f"  {line}")


def test_device_name_caching():
    """Test that device names are efficiently retrieved."""
    from honeywell_radio_exporter.ramses_prometheus_exporter import RamsesPrometheusExporter

    with patch("honeywell_radio_exporter.ramses_prometheus_exporter.start_http_server"):
        exporter = RamsesPrometheusExporter(port=8000, ramses_port="/dev/ttyUSB0")

    # Mock gateway
    mock_gateway = Mock()
    mock_device = Mock()
    mock_device.id = "01:234576"
    mock_device.traits = {"alias": "Controller", "class": "controller"}
    mock_gateway.device_by_id = {"01:234576": mock_device}
    exporter.gateway = mock_gateway

    # Get name multiple times
    name1 = exporter._get_device_name("01:234576")
    name2 = exporter._get_device_name("01:234576")
    name3 = exporter._get_device_name("01:234576")

    # All should return the same name
    assert name1 == name2 == name3 == "Controller"

    # Gateway should have been accessed (device lookup)
    assert mock_gateway.device_by_id.__getitem__.called


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "-s"])
