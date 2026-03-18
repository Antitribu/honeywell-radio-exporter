"""Unit tests for validator."""

from honeywell_radio_exporter.validator import validate_message


def test_validate_ok():
    r = validate_message(code="0001", verb="I", payload={})
    assert r.ok
    assert not r.errors


def test_validate_missing_code():
    r = validate_message(code="", verb="I", payload=None)
    assert not r.ok
    assert "code" in " ".join(r.errors).lower() or r.errors
