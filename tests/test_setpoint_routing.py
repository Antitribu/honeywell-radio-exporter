"""Setpoint: controller zone targets → zone actuators, not 01:."""

from unittest.mock import MagicMock

from honeywell_radio_exporter.message_processor import ZoneState, apply_payload


def test_trv_reports_own_setpoint_on_src():
    repo = MagicMock()
    state = ZoneState()
    apply_payload(
        repo,
        {
            "code": "2309",
            "code_name": "setpoint",
            "src_id": "04:122502",
            "dst_id": "01:234576",
            "payload": {"zone_idx": "03", "setpoint": 18.0},
        },
        state,
    )
    repo.update_device_setpoint.assert_called_once_with("04:122502", 18.0)


def test_controller_zone_mode_distributes_to_zone_devices():
    repo = MagicMock()
    state = ZoneState()
    state.zone_devices["08"] = {"0": ["04:100001", "04:100002"]}
    apply_payload(
        repo,
        {
            "code": "2349",
            "code_name": "zone_mode",
            "src_id": "01:234576",
            "dst_id": "18:147744",
            "payload": {"zone_idx": "08", "mode": "follow_schedule", "setpoint": 6.0},
        },
        state,
    )
    assert repo.update_device_setpoint.call_count == 2
    ids = {c[0][0] for c in repo.update_device_setpoint.call_args_list}
    assert ids == {"04:100001", "04:100002"}
    assert all(c[0][1] == 6.0 for c in repo.update_device_setpoint.call_args_list)


def test_controller_setpoint_not_written_to_controller_when_no_zone_map():
    repo = MagicMock()
    state = ZoneState()
    apply_payload(
        repo,
        {
            "code": "2309",
            "code_name": "setpoint",
            "src_id": "01:234576",
            "dst_id": "",
            "payload": {"zone_idx": "0A", "setpoint": 10.0},
        },
        state,
    )
    repo.update_device_setpoint.assert_not_called()


def test_controller_setpoint_list_per_zone():
    repo = MagicMock()
    state = ZoneState()
    state.zone_devices["00"] = {"0": ["04:111"]}
    state.zone_devices["01"] = {"0": ["04:222"]}
    apply_payload(
        repo,
        {
            "code": "2309",
            "code_name": "setpoint",
            "src_id": "01:234576",
            "dst_id": "",
            "payload": [
                {"zone_idx": "00", "setpoint": 19.0},
                {"zone_idx": "01", "setpoint": 20.0},
            ],
        },
        state,
    )
    assert repo.update_device_setpoint.call_count == 2
    repo.update_device_setpoint.assert_any_call("04:111", 19.0)
    repo.update_device_setpoint.assert_any_call("04:222", 20.0)


def test_dhw_params_still_sets_controller_dhw():
    repo = MagicMock()
    state = ZoneState()
    apply_payload(
        repo,
        {
            "code": "10A0",
            "code_name": "dhw_params",
            "src_id": "01:234576",
            "dst_id": "18:147744",
            "payload": {"dhw_idx": "00", "setpoint": 50.0},
        },
        state,
    )
    repo.update_device_setpoint.assert_called_once_with("01:234576", 50.0)
