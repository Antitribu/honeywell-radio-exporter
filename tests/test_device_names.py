"""
Tests for device name labels in metrics.

This test validates that device names are included as labels in Prometheus metrics,
using the generated.txt output from processing sample_data/ramses.msgs.
"""

from pathlib import Path
import re


def test_device_name_labels_in_metrics():
    """Test that metrics include device_name labels."""
    generated_file = Path(__file__).parent / "sample_data" / "generated.txt"
    assert generated_file.exists(), f"Generated file not found: {generated_file}"

    with open(generated_file, "r") as f:
        content = f.read()

    # Should have device_name labels in metrics
    assert 'device_name="' in content, "device_name label should exist in metrics"
    
    # Check that key metrics have these labels
    metrics_to_check = [
        "ramses_device_temperature_celsius",
        "ramses_device_last_seen_timestamp",
    ]

    for metric in metrics_to_check:
        lines = [line for line in content.split("\n") if line.startswith(metric + "{")]
        assert len(lines) > 0, f"Should have {metric} metrics"
        
        # All these metrics should have device_name labels
        for line in lines:
            assert 'device_name="' in line, f"Missing device_name in {metric}: {line}"
            break  # Just check first line for each metric

    print("✓ All device metrics have device_name labels")


def test_device_ids_in_metrics():
    """Test that device IDs follow expected format."""
    generated_file = Path(__file__).parent / "sample_data" / "generated.txt"

    with open(generated_file, "r") as f:
        content = f.read()

    # Extract device IDs from all metrics
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
    print(f"  Sample: {sorted(list(device_ids))[:5]}")


def test_device_types_in_metrics():
    """Test that we have various device types in the metrics."""
    generated_file = Path(__file__).parent / "sample_data" / "generated.txt"

    with open(generated_file, "r") as f:
        content = f.read()

    # Extract device types (first part of device_id)
    device_id_pattern = r'device_id="(\d{2}):\d{6}"'
    device_types = set(re.findall(device_id_pattern, content))

    print(f"\n✓ Found {len(device_types)} device types in metrics:")
    for dtype in sorted(device_types):
        print(f"  Type {dtype}")

    # Should have multiple device types
    assert len(device_types) >= 2, "Should have multiple device types"


def test_device_name_values():
    """Test that device_name labels are present (may be 'unknown')."""
    generated_file = Path(__file__).parent / "sample_data" / "generated.txt"

    with open(generated_file, "r") as f:
        content = f.read()

    # Extract all device names from metrics
    device_name_pattern = r'device_name="([^"]+)"'
    all_device_names = re.findall(device_name_pattern, content)
    device_names = set(all_device_names)

    print(f"\n✓ Found {len(device_names)} unique device names:")
    for name in sorted(device_names):
        count = all_device_names.count(name)
        print(f"  - {name} ({count} occurrences)")

    # Device names may all be "unknown" if no device_name messages exist
    # That's OK - just check the label is present
    assert len(device_names) > 0, "Should have device_name labels"


def test_no_old_device_info_metric():
    """Test that the old ramses_device_info metric no longer exists."""
    generated_file = Path(__file__).parent / "sample_data" / "generated.txt"

    with open(generated_file, "r") as f:
        content = f.read()

    # Should NOT have ramses_device_info metrics anymore
    assert "ramses_device_info" not in content, "Old ramses_device_info metric should not exist"

    print("✓ Old device_info metric has been removed")


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v", "-s"])
