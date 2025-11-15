"""
Tests for zone name extraction and ramses_zone_info metric.

This module validates that zone names are correctly captured from RAMSES RF
messages and populated in the ramses_zone_info metric, using the generated.txt
output from processing sample_data/ramses.msgs.
"""

from pathlib import Path


def test_zone_info_metrics_in_generated_output():
    """Test that ramses_zone_info metrics exist in generated output."""
    generated_file = Path(__file__).parent / "sample_data" / "generated.txt"
    assert generated_file.exists(), f"Generated file not found: {generated_file}"

    with open(generated_file, "r") as f:
        content = f.read()

    # Should have ramses_zone_info metrics
    assert "ramses_zone_info" in content, "ramses_zone_info metric should exist"

    # Check that zone_info has both zone_idx and zone_name labels
    assert 'zone_idx="' in content, "zone_idx label should exist"
    assert 'zone_name="' in content, "zone_name label should exist"

    # Count how many zone_info metrics we have
    zone_info_lines = [line for line in content.split("\n") if line.startswith("ramses_zone_info{")]
    print(f"\n✓ Found {len(zone_info_lines)} zone_info metric(s)")
    for line in zone_info_lines:
        print(f"  {line}")


def test_zone_info_metric_structure():
    """Test that zone_info metrics have correct structure (labels and value)."""
    generated_file = Path(__file__).parent / "sample_data" / "generated.txt"

    with open(generated_file, "r") as f:
        lines = f.readlines()

    zone_info_metrics = [line for line in lines if line.startswith("ramses_zone_info{")]

    assert len(zone_info_metrics) > 0, "Should have at least one zone_info metric"

    for metric_line in zone_info_metrics:
        # Check structure: ramses_zone_info{zone_idx="...",zone_name="..."} 1.0
        assert 'zone_idx="' in metric_line, f"Missing zone_idx in: {metric_line}"
        assert 'zone_name="' in metric_line, f"Missing zone_name in: {metric_line}"
        assert "1.0" in metric_line or "1" in metric_line, f"Value should be 1.0 in: {metric_line}"

        # Should NOT have zone_name="unknown"
        assert (
            'zone_name="unknown"' not in metric_line
        ), f"Should not have unknown zones: {metric_line}"


def test_zone_info_no_unknown_zones():
    """Test that we don't create zone_info metrics for unknown zones."""
    generated_file = Path(__file__).parent / "sample_data" / "generated.txt"

    with open(generated_file, "r") as f:
        content = f.read()

    # Check that there are no zone_info metrics with zone_name="unknown"
    lines = content.split("\n")
    unknown_zone_info = [
        line
        for line in lines
        if line.startswith("ramses_zone_info{") and 'zone_name="unknown"' in line
    ]

    assert (
        len(unknown_zone_info) == 0
    ), f"Found {len(unknown_zone_info)} zone_info metrics with unknown names:\n" + "\n".join(
        unknown_zone_info[:5]
    )


def test_zone_info_ignores_zone_idx_00():
    """Test that zone_idx='00' does not create a zone_info metric."""
    generated_file = Path(__file__).parent / "sample_data" / "generated.txt"

    with open(generated_file, "r") as f:
        content = f.read()

    # Extract only ramses_zone_info section
    lines = content.split("\n")
    zone_info_lines = [line for line in lines if line.startswith("ramses_zone_info{")]

    # Check that none of the zone_info metrics have zone_idx="00"
    zone_00_metrics = [line for line in zone_info_lines if 'zone_idx="00"' in line]

    assert (
        len(zone_00_metrics) == 0
    ), f"Found zone_info metrics with zone_idx='00' (should not exist):\n" + "\n".join(
        zone_00_metrics
    )


def test_zone_indices_format():
    """Test that zone indices follow expected format (2 hex digits)."""
    generated_file = Path(__file__).parent / "sample_data" / "generated.txt"

    with open(generated_file, "r") as f:
        content = f.read()

    # Extract zone indices from zone_info metrics
    import re

    zone_idx_pattern = r'ramses_zone_info\{zone_idx="([0-9A-F]{2})"'
    zone_indices = set(re.findall(zone_idx_pattern, content))

    assert len(zone_indices) > 0, "Should find zone indices in metrics"

    # All zone indices should be 2 hex digits
    for zone_idx in zone_indices:
        assert len(zone_idx) == 2, f"Zone index should be 2 characters: {zone_idx}"
        assert zone_idx != "00", f"Zone index should not be '00': {zone_idx}"
        # Should be valid hex
        assert all(
            c in "0123456789ABCDEF" for c in zone_idx
        ), f"Zone index should be hex: {zone_idx}"

    print(f"\n✓ Found {len(zone_indices)} unique zone indices with valid format")
    print(f"  Zones: {sorted(list(zone_indices))}")


def test_expected_zones_present():
    """Test that expected zones from sample data are present."""
    generated_file = Path(__file__).parent / "sample_data" / "generated.txt"

    with open(generated_file, "r") as f:
        content = f.read()

    # Expected zones based on sample_data/ramses.msgs
    expected_zones = [
        ("01", "Kitchen"),
        ("02", "Living Room"),
        ("03", "Master Bedroom"),
        ("0A", "Office"),
    ]

    zone_info_lines = [line for line in content.split("\n") if line.startswith("ramses_zone_info{")]

    for zone_idx, zone_name in expected_zones:
        # Check if this zone exists in the metrics
        zone_exists = any(
            f'zone_idx="{zone_idx}"' in line and f'zone_name="{zone_name}"' in line
            for line in zone_info_lines
        )
        assert zone_exists, f"Expected zone {zone_idx} ({zone_name}) not found in metrics"
        print(f"✓ Found expected zone {zone_idx}: {zone_name}")


def test_all_zone_names_are_real():
    """Test that all zone names in metrics are real (not 'unknown')."""
    generated_file = Path(__file__).parent / "sample_data" / "generated.txt"

    with open(generated_file, "r") as f:
        content = f.read()

    # Extract all zone names from zone_info metrics
    import re

    zone_name_pattern = r'ramses_zone_info\{zone_idx="[^"]+",zone_name="([^"]+)"\}'
    zone_names = set(re.findall(zone_name_pattern, content))

    print(f"\n✓ Found {len(zone_names)} unique zone names:")
    for name in sorted(zone_names):
        print(f"  - {name}")

    # Should not have 'unknown' in zone names
    assert "unknown" not in zone_names, "Should not have 'unknown' zone names in zone_info metrics"

    # Should have at least a few zones
    assert len(zone_names) >= 4, f"Should have at least 4 named zones, found {len(zone_names)}"


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v", "-s"])
