"""DHW status ingestion."""

from unittest.mock import MagicMock

from honeywell_radio_exporter.dhw_log import try_record_dhw_status


def test_dhw_temp_updates_temp():
    repo = MagicMock()
    try_record_dhw_status(
        repo,
        {
            "code_name": "dhw_temp",
            "src_id": "01:234576",
            "dst_id": "18:147744",
            "payload": {"dhw_idx": "00", "temperature": 23.94},
        },
    )
    repo.merge_dhw_status.assert_called_once()
    idx, patch = repo.merge_dhw_status.call_args[0]
    assert idx == "00"
    assert abs(patch["temperature_c"] - 23.94) < 0.01
    assert patch["controller_id"] == "01:234576"


def test_dhw_params_updates_setpoint_and_params():
    repo = MagicMock()
    try_record_dhw_status(
        repo,
        {
            "code_name": "dhw_params",
            "src_id": "01:234576",
            "dst_id": "18:147744",
            "payload": {"dhw_idx": "00", "setpoint": 50.0, "overrun": 0, "differential": 10.0},
        },
    )
    idx, patch = repo.merge_dhw_status.call_args[0]
    assert idx == "00"
    assert patch["setpoint_c"] == 50.0
    assert patch["overrun"] == 0
    assert patch["differential_c"] == 10.0


def test_dhw_mode_updates_mode_and_active():
    repo = MagicMock()
    try_record_dhw_status(
        repo,
        {
            "code_name": "dhw_mode",
            "src_id": "01:234576",
            "dst_id": "18:147744",
            "payload": {"dhw_idx": "00", "mode": "follow_schedule", "active": False},
        },
    )
    idx, patch = repo.merge_dhw_status.call_args[0]
    assert idx == "00"
    assert patch["mode"] == "follow_schedule"
    assert patch["active"] is False

