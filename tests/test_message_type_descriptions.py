"""message_type_descriptions helpers."""

from honeywell_radio_exporter.message_type_descriptions import (
    description_for_message_type,
)


def test_known_type():
    d = description_for_message_type("30C9", "temperature")
    assert "30C9" in d or "temperature" in d.lower()
    assert len(d) > 40


def test_fallback_message_prefix():
    d = description_for_message_type("ABCD", "message_1234")
    assert "message_1234" in d
    assert "ABCD" in d


def test_code_only():
    d = description_for_message_type("7FFF", None)
    assert "7FFF" in d
