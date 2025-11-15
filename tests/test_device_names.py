"""
Tests for device name extraction and metrics.

This test validates that device names are correctly extracted from RAMSES RF
messages and populated in Prometheus metrics, using the generated.txt output
from processing sample_data/ramses.msgs.
"""

from pathlib import Path


def test_device_info_metrics_in_generated_output():
    """Test that ramses_device_info metrics exist in generated output."""
    generated_file = Path(__file__).parent / "sample_data" / "generated.txt"
    assert generated_file.exists(), f"Generated file not found: {generated_file}"

    with open(generated_file, "r") as f:
        content = f.read()

    # Should have ramses_device_info metrics
    assert "ramses_device_info" in content, "ramses_device_info metric should exist"

    # Check that device_info has both device_id and device_name labels
    assert 'device_id="' in content, "device_id label should exist"
    assert 'device_name="' in content, "device_name label should exist"

    # Count how many device_info metrics we have
    device_info_lines = [
        line for line in content.split("\n") if line.startswith("ramses_device_info{")
    ]
    print(f"\n✓ Found {len(device_info_lines)} device_info metric(s)")
    for line in device_info_lines[:5]:  # Show first 5
        print(f"  {line}")


def test_device_info_metric_structure():
    """Test that device_info metrics have correct structure (labels and value)."""
    generated_file = Path(__file__).parent / "sample_data" / "generated.txt"

    with open(generated_file, "r") as f:
        lines = f.readlines()

    device_info_metrics = [line for line in lines if line.startswith("ramses_device_info{")]

    assert len(device_info_metrics) > 0, "Should have at least one device_info metric"

    for metric_line in device_info_metrics:
        # Check structure: ramses_device_info{device_id="...",device_name="..."} 1.0
        assert 'device_id="' in metric_line, f"Missing device_id in: {metric_line}"
        assert 'device_name="' in metric_line, f"Missing device_name in: {metric_line}"
        assert "1.0" in metric_line or "1" in metric_line, f"Value should be 1.0 in: {metric_line}"

        # Should NOT have device_name="unknown"
        assert (
            'device_name="unknown"' not in metric_line
        ), f"Should not have unknown device names: {metric_line}"


def test_device_info_no_unknown_devices():
    """Test that we don't create device_info metrics for unknown devices."""
    generated_file = Path(__file__).parent / "sample_data" / "generated.txt"

    with open(generated_file, "r") as f:
        content = f.read()

    # Check that there are no device_info metrics with device_name="unknown"
    lines = content.split("\n")
    unknown_device_info = [
        line
        for line in lines
        if line.startswith("ramses_device_info{") and 'device_name="unknown"' in line
    ]

    assert (
        len(unknown_device_info) == 0
    ), f"Found {len(unknown_device_info)} device_info metrics with unknown names:\n" + "\n".join(
        unknown_device_info[:5]
    )


def test_device_ids_in_metrics():
    """Test that device IDs follow expected format."""
    generated_file = Path(__file__).parent / "sample_data" / "generated.txt"

    with open(generated_file, "r") as f:
        content = f.read()

    # Extract device IDs from device_info metrics
    import re

    device_id_pattern = r'device_id="(\d{2}:\d{6})"'
    device_ids = set(re.findall(device_id_pattern, content))

    assert len(device_ids) > 0, "Should find device IDs in metrics"

    # All device IDs should follow format: XX:XXXXXX
    for device_id in device_ids:
        parts = device_id.split(":")
        assert len(parts) == 2, f"Device ID should have format XX:XXXXXX: {device_id}"
        assert len(parts[0]) == 2, f"Device type should be 2 digits: {device_id}"
        assert len(parts[1]) == 6, f"Device number should be 6 digits: {device_id}"

    print(f"\n✓ Found {len(device_ids)} unique device IDs with valid format")
    print(f"  Sample: {sorted(list(device_ids))[:3]}")


def test_device_types_in_metrics():
    """Test that we have various device types in the metrics."""
    generated_file = Path(__file__).parent / "sample_data" / "generated.txt"

    with open(generated_file, "r") as f:
        content = f.read()

    # Extract device types (first part of device_id)
    import re

    device_id_pattern = r'device_id="(\d{2}):\d{6}"'
    device_types = set(re.findall(device_id_pattern, content))

    print(f"\n✓ Found {len(device_types)} device types in metrics:")
    for dtype in sorted(device_types):
        print(f"  Type {dtype}")

    # Should have multiple device types
    assert len(device_types) >= 2, "Should have multiple device types"


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v", "-s"])
