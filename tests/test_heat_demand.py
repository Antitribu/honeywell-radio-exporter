"""heat_demand (3150) → devices.heat_demand."""

from unittest.mock import MagicMock

from honeywell_radio_exporter.message_processor import ZoneState, apply_payload


def test_heat_demand_dict_updates_src_trv():
    repo = MagicMock()
    state = ZoneState()
    apply_payload(
        repo,
        {
            "code": "3150",
            "code_name": "heat_demand",
            "src_id": "04:122820",
            "dst_id": "01:234576",
            "payload": {"heat_demand": 0.42},
        },
        state,
    )
    repo.update_device_heat_demand.assert_called_once()
    assert repo.update_device_heat_demand.call_args[0][0] == "04:122820"
    assert abs(repo.update_device_heat_demand.call_args[0][1] - 42.0) < 0.01


def test_heat_demand_list_updates_zone_devices():
    repo = MagicMock()
    state = ZoneState()
    state.zone_devices["03"] = {"role": ["04:111111", "04:222222"]}
    apply_payload(
        repo,
        {
            "code": "3150",
            "code_name": "heat_demand",
            "src_id": "01:234576",
            "dst_id": "01:234576",
            "payload": [{"zone_idx": "03", "heat_demand": 0.5}],
        },
        state,
    )
    assert repo.update_device_heat_demand.call_count == 2
    ids = {c[0][0] for c in repo.update_device_heat_demand.call_args_list}
    assert ids == {"04:111111", "04:222222"}
