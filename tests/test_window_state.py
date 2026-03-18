"""12B0 window_state → devices.window_state."""

from unittest.mock import MagicMock

from honeywell_radio_exporter.message_processor import ZoneState, apply_payload


def test_window_state_trv_reports_src():
    repo = MagicMock()
    apply_payload(
        repo,
        {
            "code": "12B0",
            "code_name": "window_state",
            "src_id": "04:122504",
            "dst_id": "01:234576",
            "payload": {"zone_idx": "01", "window_open": False},
        },
        ZoneState(),
    )
    repo.update_device_window_state.assert_called_once_with("04:122504", "closed")


def test_window_state_controller_rp_zone():
    repo = MagicMock()
    state = ZoneState()
    state.zone_devices["08"] = {"0": ["04:100001", "04:100002"]}
    apply_payload(
        repo,
        {
            "code": "12B0",
            "code_name": "window_state",
            "src_id": "01:234576",
            "dst_id": "18:147744",
            "payload": {"zone_idx": "08", "window_open": True},
        },
        state,
    )
    assert repo.update_device_window_state.call_count == 2
    for call in repo.update_device_window_state.call_args_list:
        assert call[0][0] in ("04:100001", "04:100002")
        assert call[0][1] == "open"
