"""fault_log ingestion."""

from unittest.mock import MagicMock

from honeywell_radio_exporter.fault_log import (
    normalize_fault_event_timestamp,
    try_record_fault_log,
)


def test_normalize_fault_event_timestamp_2y_to_4y():
    assert normalize_fault_event_timestamp("25-11-15T10:00:00") == "2025-11-15T10:00:00"
    assert normalize_fault_event_timestamp("23-01-01T00:00:00") == "2023-01-01T00:00:00"


def test_normalize_fault_event_timestamp_already_4y():
    assert (
        normalize_fault_event_timestamp("2023-11-17T20:03:18") == "2023-11-17T20:03:18"
    )


def test_normalize_fault_event_timestamp_passthrough():
    assert normalize_fault_event_timestamp("weird") == "weird"
    assert normalize_fault_event_timestamp(None) is None
    assert normalize_fault_event_timestamp("") is None


def test_try_record_skips_rq():
    repo = MagicMock()
    try_record_fault_log(
        repo,
        {
            "verb": "RQ",
            "code": "0418",
            "payload": {"log_idx": "00", "log_entry": ("t", "fault", "battery_low")},
        },
    )
    repo.insert_fault_log_entry.assert_not_called()


def test_try_record_inserts_rp():
    repo = MagicMock()
    try_record_fault_log(
        repo,
        {
            "verb": "RP",
            "code": "0418",
            "code_name": "system_fault",
            "src_id": "01:234576",
            "dst_id": "18:147744",
            "payload": {
                "log_idx": "05",
                "log_entry": (
                    "25-11-15T10:00:00",
                    "fault",
                    "battery_low",
                    "actuator",
                    "04:122498",
                ),
            },
        },
    )
    repo.insert_fault_log_entry.assert_called_once()
    kw = repo.insert_fault_log_entry.call_args.kwargs
    assert kw["log_idx"] == "05"
    assert kw["event_timestamp"] == "2025-11-15T10:00:00"
    assert kw["fault_state"] == "fault"
    assert kw["fault_type"] == "battery_low"
    assert kw["device_id"] == "04:122498"
