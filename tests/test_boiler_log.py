"""OpenTherm bridge boiler_status ingestion."""

from unittest.mock import MagicMock

from honeywell_radio_exporter.boiler_log import try_record_boiler_telemetry


def test_3ef0_updates_flags():
    repo = MagicMock()
    try_record_boiler_telemetry(
        repo,
        {
            "code": "3EF0",
            "code_name": "actuator_state",
            "src_id": "10:123456",
            "payload": {
                "flame_on": True,
                "ch_active": True,
                "dhw_active": False,
                "modulation_level": 0.5,
            },
        },
    )
    repo.merge_boiler_otb.assert_called_once()
    kw = repo.merge_boiler_otb.call_args[0]
    assert kw[0] == "10:123456"
    p = kw[1]
    assert p["flame_on"] is True
    assert p["ch_active"] is True
    assert p["dhw_active"] is False
    assert abs(p["modulation_pct"] - 50.0) < 0.1


def test_ignores_non_otb():
    repo = MagicMock()
    try_record_boiler_telemetry(
        repo,
        {
            "code": "3200",
            "src_id": "04:122820",
            "payload": {"temperature": 55.0},
        },
    )
    repo.merge_boiler_otb.assert_not_called()


def test_3200_flow():
    repo = MagicMock()
    try_record_boiler_telemetry(
        repo,
        {
            "code": "3200",
            "code_name": "boiler_output",
            "src_id": "10:111111",
            "payload": {"temperature": 48.5},
        },
    )
    repo.merge_boiler_otb.assert_called_once_with(
        "10:111111", {"flow_temp_c": 48.5}
    )


def test_relay_13_relay_demand_0008():
    repo = MagicMock()
    try_record_boiler_telemetry(
        repo,
        {
            "code": "0008",
            "code_name": "relay_demand",
            "src_id": "13:243590",
            "dst_id": "18:147744",
            "payload": {"relay_demand": 0.75},
        },
    )
    repo.merge_boiler_otb.assert_called_once_with(
        "13:243590",
        {"modulation_pct": 75.0, "ch_active": True},
    )


def test_relay_13_3ef0_modulation_only():
    repo = MagicMock()
    try_record_boiler_telemetry(
        repo,
        {
            "code": "3EF0",
            "code_name": "actuator_state",
            "src_id": "13:106039",
            "payload": {"modulation_level": 1.0, "_flags_2": "FF"},
        },
    )
    repo.merge_boiler_otb.assert_called_once()
    p = repo.merge_boiler_otb.call_args[0][1]
    assert p["modulation_pct"] == 100.0
    assert p["ch_active"] is True


def test_relay_13_zero_demand():
    repo = MagicMock()
    try_record_boiler_telemetry(
        repo,
        {
            "code": "0008",
            "code_name": "relay_demand",
            "src_id": "13:004003",
            "payload": {"relay_demand": 0.0},
        },
    )
    repo.merge_boiler_otb.assert_called_once_with(
        "13:004003",
        {"modulation_pct": 0.0, "ch_active": False},
    )
