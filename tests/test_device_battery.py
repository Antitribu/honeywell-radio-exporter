"""1060 device_battery → devices."""

from unittest.mock import MagicMock

from honeywell_radio_exporter.message_processor import ZoneState, apply_payload


def test_device_battery_with_level():
    repo = MagicMock()
    apply_payload(
        repo,
        {
            "code": "1060",
            "code_name": "device_battery",
            "src_id": "04:122820",
            "dst_id": "01:234576",
            "payload": {"battery_level": 0.85, "battery_low": False},
        },
        ZoneState(),
    )
    repo.update_device_battery.assert_called_once_with("04:122820", 85.0, False)


def test_device_battery_low_only():
    repo = MagicMock()
    apply_payload(
        repo,
        {
            "code": "1060",
            "code_name": "device_battery",
            "src_id": "04:122820",
            "payload": {"battery_level": None, "battery_low": True},
        },
        ZoneState(),
    )
    repo.update_device_battery.assert_called_once_with("04:122820", None, True)
