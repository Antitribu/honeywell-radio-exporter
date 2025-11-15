"""
Validate that all expected metrics have data from sample messages.

This test analyzes sample_data/ramses.msgs and generated.txt to ensure
that metrics are correctly generated from available message data.
"""

import pytest
import ast
from pathlib import Path
from collections import defaultdict


def parse_ramses_message_line(line: str) -> dict:
    """
    Parse a line from ramses.msgs format.

    Format: ||  device1 |  device2 |  verb | message_type | context || payload_dict
    Example: ||  01:234576 |  18:147744 | RP | zone_mode | 08 || {'zone_idx': '08', 'mode': 'follow_schedule'}
    """
    if not line.strip() or not line.startswith("||"):
        return None

    try:
        # Split on || to separate header from payload
        parts = line.split("||")
        if len(parts) < 3:
            return None

        # Parse header: device1 | device2 | verb | message_type | context
        header = parts[1].strip()
        header_parts = [p.strip() for p in header.split("|")]
        if len(header_parts) < 4:
            return None

        device1 = header_parts[0]
        device2 = header_parts[1] if len(header_parts) > 1 else ""
        verb = header_parts[2] if len(header_parts) > 2 else ""
        message_type = header_parts[3] if len(header_parts) > 3 else ""
        context = header_parts[4] if len(header_parts) > 4 else ""

        # Parse payload (Python dict as string)
        payload_str = parts[2].strip()
        if payload_str:
            payload = ast.literal_eval(payload_str)
        else:
            payload = {}

        return {
            "device1": device1,
            "device2": device2,
            "verb": verb,
            "message_type": message_type,
            "context": context,
            "payload": payload,
        }
    except Exception as e:
        # Skip lines that can't be parsed
        return None


def test_sample_data_parsing():
    """Test that we can parse sample data correctly."""
    test_dir = Path(__file__).parent
    input_file = test_dir / "sample_data" / "ramses.msgs"

    assert input_file.exists(), f"Sample data not found: {input_file}"

    parsed_count = 0
    failed_count = 0

    with open(input_file, "r") as f:
        for line in f:
            result = parse_ramses_message_line(line)
            if result:
                parsed_count += 1
            elif line.strip() and line.startswith("||"):
                failed_count += 1

    print(f"\nParsed {parsed_count} messages, {failed_count} failed")
    assert parsed_count > 0, "No messages parsed successfully"
    assert parsed_count > 2000, f"Expected > 2000 messages, got {parsed_count}"


def test_zone_mode_data_exists():
    """Validate that zone_mode data exists in sample messages."""
    test_dir = Path(__file__).parent
    input_file = test_dir / "sample_data" / "ramses.msgs"

    zone_modes = []

    with open(input_file, "r") as f:
        for line in f:
            msg = parse_ramses_message_line(line)
            if msg and msg["message_type"] == "zone_mode":
                if isinstance(msg["payload"], dict) and "mode" in msg["payload"]:
                    zone_modes.append(msg["payload"])

    print(f"\nFound {len(zone_modes)} zone_mode messages with mode data")
    assert len(zone_modes) > 0, "No zone_mode messages found"

    # Check that modes are present
    modes = [m["mode"] for m in zone_modes if "mode" in m]
    unique_modes = set(modes)
    print(f"Unique modes: {unique_modes}")

    assert "follow_schedule" in unique_modes, "Missing 'follow_schedule' mode"

    # This should fail if ramses_zone_mode_info is not populated
    output_file = test_dir / "sample_data" / "generated.txt"
    if output_file.exists():
        with open(output_file, "r") as f:
            content = f.read()
            # Check if ramses_zone_mode_info has actual data points
            has_mode_data = "ramses_zone_mode_info{" in content and "mode=" in content
            if not has_mode_data:
                pytest.fail(
                    f"ramses_zone_mode_info metric has no data points despite {len(zone_modes)} "
                    f"zone_mode messages with mode information in sample data"
                )


def test_setpoint_data_exists():
    """Validate that setpoint data exists and is captured."""
    test_dir = Path(__file__).parent
    input_file = test_dir / "sample_data" / "ramses.msgs"

    setpoints = []

    with open(input_file, "r") as f:
        for line in f:
            msg = parse_ramses_message_line(line)
            if not msg:
                continue

            payload = msg["payload"]

            # Check various message types that contain setpoint
            if msg["message_type"] == "setpoint" and isinstance(payload, list):
                for item in payload:
                    if isinstance(item, dict) and "setpoint" in item:
                        setpoints.append(item)
            elif isinstance(payload, dict) and "setpoint" in payload:
                setpoints.append(payload)

    print(f"\nFound {len(setpoints)} setpoint values in sample messages")
    assert len(setpoints) > 0, "No setpoint data found"

    # Check generated metrics
    output_file = test_dir / "sample_data" / "generated.txt"
    if output_file.exists():
        with open(output_file, "r") as f:
            content = f.read()
            has_setpoint_data = "ramses_device_setpoint_celsius{" in content
            if not has_setpoint_data:
                pytest.fail(
                    f"ramses_device_setpoint_celsius has no data points despite {len(setpoints)} "
                    f"setpoint values in sample data"
                )


def test_window_state_data_exists():
    """Validate that window state data exists and is captured."""
    test_dir = Path(__file__).parent
    input_file = test_dir / "sample_data" / "ramses.msgs"

    window_states = []

    with open(input_file, "r") as f:
        for line in f:
            msg = parse_ramses_message_line(line)
            if msg and msg["message_type"] == "window_state":
                if isinstance(msg["payload"], dict) and "window_open" in msg["payload"]:
                    window_states.append(msg["payload"])

    print(f"\nFound {len(window_states)} window_state messages")
    assert len(window_states) > 0, "No window_state messages found"

    # Check generated metrics
    output_file = test_dir / "sample_data" / "generated.txt"
    if output_file.exists():
        with open(output_file, "r") as f:
            content = f.read()
            has_window_data = "ramses_zone_window_open{" in content
            if not has_window_data:
                pytest.fail(
                    f"ramses_zone_window_open has no data points despite {len(window_states)} "
                    f"window_state messages in sample data"
                )


def test_heat_demand_data_exists():
    """Validate that heat demand data exists and is captured."""
    test_dir = Path(__file__).parent
    input_file = test_dir / "sample_data" / "ramses.msgs"

    heat_demands = []

    with open(input_file, "r") as f:
        for line in f:
            msg = parse_ramses_message_line(line)
            if msg and msg["message_type"] == "heat_demand":
                if isinstance(msg["payload"], dict) and "heat_demand" in msg["payload"]:
                    heat_demands.append(msg["payload"])

    print(f"\nFound {len(heat_demands)} heat_demand messages")
    assert len(heat_demands) > 0, "No heat_demand messages found"

    # Check generated metrics
    output_file = test_dir / "sample_data" / "generated.txt"
    if output_file.exists():
        with open(output_file, "r") as f:
            content = f.read()
            has_demand_data = "ramses_heat_demand{" in content
            if not has_demand_data:
                pytest.fail(
                    f"ramses_heat_demand has no data points despite {len(heat_demands)} "
                    f"heat_demand messages in sample data"
                )


def test_temperature_data_exists():
    """Validate that temperature data exists and is captured."""
    test_dir = Path(__file__).parent
    input_file = test_dir / "sample_data" / "ramses.msgs"

    temperatures = []

    with open(input_file, "r") as f:
        for line in f:
            msg = parse_ramses_message_line(line)
            if not msg:
                continue

            payload = msg["payload"]

            # Temperature can be in arrays or single dict
            if msg["message_type"] == "temperature" and isinstance(payload, list):
                for item in payload:
                    if isinstance(item, dict) and "temperature" in item:
                        temperatures.append(item)
            elif isinstance(payload, dict) and "temperature" in payload:
                temperatures.append(payload)

    print(f"\nFound {len(temperatures)} temperature values")
    assert len(temperatures) > 0, "No temperature data found"

    # Check generated metrics
    output_file = test_dir / "sample_data" / "generated.txt"
    if output_file.exists():
        with open(output_file, "r") as f:
            content = f.read()
            has_temp_data = "ramses_device_temperature_celsius{" in content
            if not has_temp_data:
                pytest.fail(
                    f"ramses_device_temperature_celsius has no data points despite {len(temperatures)} "
                    f"temperature values in sample data"
                )


def test_zone_name_data_exists():
    """Validate that zone name data exists and is captured."""
    test_dir = Path(__file__).parent
    input_file = test_dir / "sample_data" / "ramses.msgs"

    zone_names = []

    with open(input_file, "r") as f:
        for line in f:
            msg = parse_ramses_message_line(line)
            if msg and msg["message_type"] == "zone_name":
                if isinstance(msg["payload"], dict) and "name" in msg["payload"]:
                    zone_names.append(msg["payload"])

    print(f"\nFound {len(zone_names)} zone_name messages")
    print(f"Unique zone names: {set(z['name'] for z in zone_names if 'name' in z)}")

    assert len(zone_names) > 0, "No zone_name messages found"

    # Check generated metrics
    output_file = test_dir / "sample_data" / "generated.txt"
    if output_file.exists():
        with open(output_file, "r") as f:
            content = f.read()
            has_zone_info = "ramses_zone_info{" in content
            if not has_zone_info:
                pytest.fail(
                    f"ramses_zone_info has no data points despite {len(zone_names)} "
                    f"zone_name messages in sample data"
                )


def test_zone_name_office_in_generated_metrics():
    """
    Validate that 'Office' zone name appears in generated metrics.

    This test depends on generated.txt existing (from test_sample_data_metrics_generation).
    It checks that ramses_zone_info contains a metric with zone_name="Office".
    """
    test_dir = Path(__file__).parent
    output_file = test_dir / "sample_data" / "generated.txt"

    # Ensure the generated file exists
    if not output_file.exists():
        pytest.skip("generated.txt does not exist. Run test_sample_data_metrics_generation first.")

    # Read the generated metrics
    with open(output_file, "r") as f:
        content = f.read()

    # Check for ramses_zone_info metric with Office label
    has_zone_info = "ramses_zone_info" in content
    assert has_zone_info, "ramses_zone_info metric not found in generated output"

    # Look for the Office zone specifically
    has_office = 'zone_name="Office"' in content

    if not has_office:
        # Print available zone names for debugging
        import re

        zone_names = re.findall(r'zone_name="([^"]+)"', content)
        unique_zones = set(zone_names)
        pytest.fail(
            f"Zone name 'Office' not found in ramses_zone_info metric. "
            f"Available zone names: {sorted(unique_zones)}"
        )

    # Verify the full metric line exists
    office_metric_pattern = r'ramses_zone_info\{zone_idx="[^"]+",zone_name="Office"\} 1\.0'
    import re

    office_metrics = re.findall(office_metric_pattern, content)

    assert len(office_metrics) > 0, (
        f"Expected at least one ramses_zone_info metric with zone_name='Office', "
        f"found {len(office_metrics)}"
    )

    print(f"\n✓ Found {len(office_metrics)} Office zone metric(s):")
    for metric in office_metrics:
        print(f"  {metric}")


def test_all_metrics_summary():
    """Generate a comprehensive summary of what data exists vs what's captured."""
    test_dir = Path(__file__).parent
    input_file = test_dir / "sample_data" / "ramses.msgs"
    output_file = test_dir / "sample_data" / "generated.txt"

    # Count available data in sample messages
    data_counts = defaultdict(int)

    with open(input_file, "r") as f:
        for line in f:
            msg = parse_ramses_message_line(line)
            if not msg:
                continue

            payload = msg["payload"]

            # Count various data types
            if isinstance(payload, dict):
                if "mode" in payload:
                    data_counts["zone_mode"] += 1
                if "setpoint" in payload:
                    data_counts["setpoint"] += 1
                if "window_open" in payload:
                    data_counts["window_state"] += 1
                if "heat_demand" in payload:
                    data_counts["heat_demand"] += 1
                if "temperature" in payload:
                    data_counts["temperature"] += 1
                if "name" in payload:
                    data_counts["zone_name"] += 1
                if "remaining_seconds" in payload:
                    data_counts["system_sync"] += 1
            elif isinstance(payload, list):
                for item in payload:
                    if isinstance(item, dict):
                        if "setpoint" in item:
                            data_counts["setpoint"] += 1
                        if "temperature" in item:
                            data_counts["temperature"] += 1

    print("\n" + "=" * 80)
    print("Data Availability Summary")
    print("=" * 80)
    for key, count in sorted(data_counts.items()):
        print(f"  {key:20s}: {count:4d} messages")

    # Check what's in generated metrics
    if output_file.exists():
        with open(output_file, "r") as f:
            content = f.read()

        print("\n" + "=" * 80)
        print("Metric Generation Status")
        print("=" * 80)

        checks = [
            ("zone_mode", "ramses_zone_mode_info{", data_counts["zone_mode"]),
            ("setpoint", "ramses_device_setpoint_celsius{", data_counts["setpoint"]),
            ("window_state", "ramses_zone_window_open{", data_counts["window_state"]),
            ("heat_demand", "ramses_heat_demand{", data_counts["heat_demand"]),
            ("temperature", "ramses_device_temperature_celsius{", data_counts["temperature"]),
            ("zone_name", "ramses_zone_info{", data_counts["zone_name"]),
        ]

        failures = []

        for name, metric_pattern, available_count in checks:
            has_data = metric_pattern in content
            status = "✓" if has_data else "✗"
            print(
                f"  {status} {name:20s}: {'HAS DATA' if has_data else 'NO DATA':10s} (available: {available_count})"
            )

            if not has_data and available_count > 0:
                failures.append((name, available_count))

        if failures:
            print("\n" + "=" * 80)
            print("FAILURES DETECTED")
            print("=" * 80)
            for name, count in failures:
                print(f"  ✗ {name}: {count} messages available but metric has no data")

            pytest.fail(
                f"{len(failures)} metrics have no data despite available messages: "
                f"{', '.join(f[0] for f in failures)}"
            )
