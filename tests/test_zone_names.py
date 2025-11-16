"""
Tests for zone name extraction in metrics.

This module validates that zone names are correctly captured from RAMSES RF
messages and populated as labels in device metrics, using the generated.txt
output from processing sample_data/ramses.msgs.
"""

from pathlib import Path
import re


def test_zone_name_labels_in_metrics():
    """Test that metrics include zone_name labels."""
    generated_file = Path(__file__).parent / "sample_data" / "generated.txt"
    assert generated_file.exists(), f"Generated file not found: {generated_file}"

    with open(generated_file, "r") as f:
        content = f.read()

    # Should have zone_name labels in metrics
    assert 'zone_name="' in content, "zone_name label should exist in metrics"
    assert 'device_name="' in content, "device_name label should exist in metrics"

    # Check that key metrics have these labels
    metrics_to_check = [
        "ramses_device_temperature_celsius",
        "ramses_device_setpoint_celsius",
        "ramses_heat_demand",
    ]

    for metric in metrics_to_check:
        lines = [line for line in content.split("\n") if line.startswith(metric + "{")]
        assert len(lines) > 0, f"Should have {metric} metrics"
        
        # All these metrics should have zone_name labels
        for line in lines:
            assert 'zone_name="' in line, f"Missing zone_name in {metric}: {line}"
            print(f"✓ {metric} has zone_name label")
            break  # Just check first line for each metric


def test_zone_names_populated_correctly():
    """Test that zone names are populated (not all unknown)."""
    generated_file = Path(__file__).parent / "sample_data" / "generated.txt"

    with open(generated_file, "r") as f:
        content = f.read()

    # Extract all zone names from device metrics
    zone_name_pattern = r'zone_name="([^"]+)"'
    all_zone_names = re.findall(zone_name_pattern, content)
    zone_names = set(all_zone_names)

    print(f"\n✓ Found {len(zone_names)} unique zone names:")
    for name in sorted(zone_names):
        count = all_zone_names.count(name)
        print(f"  - {name} ({count} occurrences)")

    # Should have at least a few real zones (not all unknown)
    real_zones = [name for name in zone_names if name != "unknown"]
    assert len(real_zones) >= 4, f"Should have at least 4 named zones, found {len(real_zones)}"

    print(f"\n✓ {len(real_zones)} zones have real names (not 'unknown')")


def test_device_names_present():
    """Test that device_name labels are present in metrics."""
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


def test_expected_zones_in_metrics():
    """Test that expected zones from sample data appear in metrics."""
    generated_file = Path(__file__).parent / "sample_data" / "generated.txt"

    with open(generated_file, "r") as f:
        content = f.read()

    # Expected zones based on sample_data/ramses.msgs (updated after sanitization)
    expected_zones = [
        "Living Room",
        "Kitchen",
        "Master Bedroom",
        "Office",
    ]

    for zone_name in expected_zones:
        # Check if this zone exists in any metric
        zone_exists = f'zone_name="{zone_name}"' in content
        assert zone_exists, f"Expected zone '{zone_name}' not found in metrics"
        print(f"✓ Found expected zone: {zone_name}")


def test_metrics_structure_consistent():
    """Test that all device metrics have consistent label structure."""
    generated_file = Path(__file__).parent / "sample_data" / "generated.txt"

    with open(generated_file, "r") as f:
        content = f.read()

    # Check temperature metrics
    temp_lines = [
        line for line in content.split("\n") 
        if line.startswith("ramses_device_temperature_celsius{")
    ]
    
    assert len(temp_lines) > 0, "Should have temperature metrics"

    for line in temp_lines:
        # Should have device_id, device_name, and zone_name
        assert 'device_id="' in line, f"Missing device_id: {line}"
        assert 'device_name="' in line, f"Missing device_name: {line}"
        assert 'zone_name="' in line, f"Missing zone_name: {line}"

    print(f"\n✓ All {len(temp_lines)} temperature metrics have correct label structure")

    # Check setpoint metrics
    setpoint_lines = [
        line for line in content.split("\n") 
        if line.startswith("ramses_device_setpoint_celsius{")
    ]
    
    assert len(setpoint_lines) > 0, "Should have setpoint metrics"

    for line in setpoint_lines:
        # Should have device_id, device_name, zone_idx, and zone_name
        assert 'device_id="' in line, f"Missing device_id: {line}"
        assert 'device_name="' in line, f"Missing device_name: {line}"
        assert 'zone_idx="' in line, f"Missing zone_idx: {line}"
        assert 'zone_name="' in line, f"Missing zone_name: {line}"

    print(f"✓ All {len(setpoint_lines)} setpoint metrics have correct label structure")

    # Check heat demand metrics
    heat_demand_lines = [
        line for line in content.split("\n") 
        if line.startswith("ramses_heat_demand{")
    ]
    
    assert len(heat_demand_lines) > 0, "Should have heat demand metrics"

    for line in heat_demand_lines:
        # Should have device_id, device_name, zone_idx, and zone_name
        assert 'device_id="' in line, f"Missing device_id: {line}"
        assert 'device_name="' in line, f"Missing device_name: {line}"
        assert 'zone_idx="' in line, f"Missing zone_idx: {line}"
        assert 'zone_name="' in line, f"Missing zone_name: {line}"

    print(f"✓ All {len(heat_demand_lines)} heat demand metrics have correct label structure")


def test_no_old_zone_info_metric():
    """Test that the old ramses_zone_info metric no longer exists."""
    generated_file = Path(__file__).parent / "sample_data" / "generated.txt"

    with open(generated_file, "r") as f:
        content = f.read()

    # Should NOT have ramses_zone_info metrics anymore
    assert "ramses_zone_info" not in content, "Old ramses_zone_info metric should not exist"
    assert "ramses_device_info" not in content, "Old ramses_device_info metric should not exist"

    print("✓ Old info metrics have been removed")


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v", "-s"])
