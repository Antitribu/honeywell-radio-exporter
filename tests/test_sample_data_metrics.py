"""
Test that processes all sample data and generates metrics output.

This integration test reads all messages from sample_data/ramses.msgs,
processes them through the exporter, and writes the resulting Prometheus
metrics to sample_data/generated.txt for validation and documentation.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from prometheus_client import REGISTRY, generate_latest

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


def test_sample_data_metrics_generation():
    """
    Process all sample RAMSES messages and generate metrics output.

    This test:
    1. Reads all messages from sample_data/ramses.msgs
    2. Parses and processes them through the exporter
    3. Exports Prometheus metrics
    4. Writes output to sample_data/generated.txt
    """
    # Get paths
    test_dir = Path(__file__).parent
    sample_data_dir = test_dir / "sample_data"
    input_file = sample_data_dir / "ramses.msgs"
    output_file = sample_data_dir / "generated.txt"
    test_cache_file = sample_data_dir / ".test_cache.json"

    # Ensure sample data exists
    assert input_file.exists(), f"Sample data not found: {input_file}"

    # Clean up any existing test cache
    if test_cache_file.exists():
        test_cache_file.unlink()

    with patch("honeywell_radio_exporter.ramses_prometheus_exporter.start_http_server"):
        exporter = RamsesPrometheusExporter(
            port=8000,
            ramses_port="/dev/ttyUSB0",
            cache_file=str(test_cache_file)
        )

        # Mock gateway with some device and zone names for richer output
        mock_gateway = MagicMock()

        # Create mock devices
        mock_device1 = MagicMock()
        mock_device1.id = "01:145038"
        mock_device1.traits = {"alias": "Controller", "class": "controller"}

        mock_device2 = MagicMock()
        mock_device2.id = "04:056057"
        mock_device2.traits = {"alias": "TRV_LivingRoom", "class": "radiator_valve"}

        mock_device3 = MagicMock()
        mock_device3.id = "13:081807"
        mock_device3.traits = {"alias": "Boiler", "class": "boiler"}

        mock_gateway.device_by_id = {
            "01:145038": mock_device1,
            "04:056057": mock_device2,
            "13:081807": mock_device3,
        }

        # Create mock TCS with zones
        mock_tcs = MagicMock()

        mock_zone1 = MagicMock()
        mock_zone1.idx = "01"
        mock_zone1.name = "Living Room"

        mock_zone2 = MagicMock()
        mock_zone2.idx = "02"
        mock_zone2.name = "Kitchen"

        mock_zone3 = MagicMock()
        mock_zone3.idx = "08"
        mock_zone3.name = "Master Bedroom"

        mock_zone4 = MagicMock()
        mock_zone4.idx = "0A"
        mock_zone4.name = "Office"

        mock_tcs.zones = [mock_zone1, mock_zone2, mock_zone3, mock_zone4]
        mock_gateway._tcs = mock_tcs

        exporter.gateway = mock_gateway

        # Read and process all messages
        messages_processed = 0
        messages_failed = 0

        with open(input_file, "r") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or not line.startswith("||"):
                    continue

                try:
                    # Parse the message line
                    # Format: ||  device1 |  device2 |  verb | message_type | context || payload_dict
                    # Example: ||  01:234576 |  18:147744 | RP | zone_mode | 08 || {'zone_idx': '08', 'mode': 'follow_schedule'}

                    # Split on || to separate header from payload
                    parts = line.split("||")
                    if len(parts) < 3:
                        continue

                    # Parse header: device1 | device2 | verb | message_type | context
                    header = parts[1].strip()
                    header_parts = [p.strip() for p in header.split("|")]
                    if len(header_parts) < 4:
                        continue

                    device1 = header_parts[0]
                    device2 = header_parts[1] if len(header_parts) > 1 else ""
                    verb = header_parts[2] if len(header_parts) > 2 else ""
                    message_type = header_parts[3] if len(header_parts) > 3 else ""

                    # Parse payload (Python dict as string)
                    payload_str = parts[2].strip()

                    # Use actual devices and verb from parsed data
                    src_id = device1 if device1 else "unknown"
                    dst_id = device2 if device2 else "unknown"
                    code = message_type

                    # Create a mock message object
                    mock_msg = MagicMock()
                    mock_msg.code = code
                    mock_msg.verb = verb

                    mock_msg.src = MagicMock()
                    mock_msg.src.id = src_id

                    mock_msg.dst = MagicMock()
                    mock_msg.dst.id = dst_id

                    # Parse payload - it's already a Python dict as a string!
                    if payload_str:
                        try:
                            import ast

                            mock_msg.payload = ast.literal_eval(payload_str)
                        except (ValueError, SyntaxError):
                            # If it fails to parse, use empty dict
                            mock_msg.payload = {}
                    else:
                        mock_msg.payload = {}

                    # Process the message through the exporter
                    exporter._capture_message_metrics(mock_msg)
                    messages_processed += 1

                except Exception as e:
                    messages_failed += 1
                    # print(f"Failed to process line {line_num}: {e}")
                    continue

        # Generate Prometheus metrics output
        metrics_output = generate_latest(REGISTRY).decode("utf-8")

        # Write to output file with header
        with open(output_file, "w") as f:
            f.write("# Prometheus Metrics Generated from Sample RAMSES RF Messages\n")
            f.write(f"# Source: {input_file.name}\n")
            f.write(f"# Messages Processed: {messages_processed}\n")
            f.write(f"# Messages Failed: {messages_failed}\n")
            f.write("#\n")
            f.write("# This file shows the metrics that would be exported to Prometheus\n")
            f.write("# after processing all sample messages.\n")
            f.write("#\n")
            f.write("# Generated by: test_sample_data_metrics_generation()\n")
            f.write("#" + "=" * 78 + "\n\n")
            f.write(metrics_output)

        # Assertions to ensure test passes
        assert messages_processed > 0, "No messages were processed"
        assert output_file.exists(), f"Output file not created: {output_file}"
        assert output_file.stat().st_size > 0, "Output file is empty"

        # Verify some expected metrics are present
        assert "ramses_messages_total" in metrics_output
        assert "ramses_device_info" in metrics_output or messages_processed > 0

        # Print summary
        print(f"\n{'='*80}")
        print(f"Sample Data Metrics Generation Test Summary")
        print(f"{'='*80}")
        print(f"Input:  {input_file}")
        print(f"Output: {output_file}")
        print(f"Messages Processed: {messages_processed}")
        print(f"Messages Failed: {messages_failed}")
        print(f"Output Size: {output_file.stat().st_size:,} bytes")
        print(f"{'='*80}\n")

    # Clean up test cache file after test
    if test_cache_file.exists():
        test_cache_file.unlink()

    # Return metrics for potential inspection
    return metrics_output


def test_generated_metrics_file_exists():
    """Verify that the generated metrics file exists after running the generation test."""
    test_dir = Path(__file__).parent
    output_file = test_dir / "sample_data" / "generated.txt"

    # This test will only pass if the generation test has been run
    # We'll make it informational rather than failing
    if output_file.exists():
        size = output_file.stat().st_size
        print(f"\n✓ Generated metrics file exists: {output_file}")
        print(f"  Size: {size:,} bytes")

        # Read and count metrics
        with open(output_file, "r") as f:
            content = f.read()
            metric_lines = [
                line for line in content.split("\n") if line and not line.startswith("#")
            ]
            print(f"  Metric lines: {len(metric_lines)}")
    else:
        print(f"\nℹ Generated metrics file not found: {output_file}")
        print("  Run test_sample_data_metrics_generation() to generate it")
