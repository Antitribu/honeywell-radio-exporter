"""Tests for runtime version / USB metadata helpers."""

from pathlib import Path

from honeywell_radio_exporter.runtime_versions import (
    gather_runtime_versions,
    get_ramses_tx_version,
)


def test_get_ramses_tx_version_from_file(tmp_path: Path) -> None:
    (tmp_path / "ramses_tx").mkdir()
    (tmp_path / "ramses_tx" / "version.py").write_text(
        '__version__ = "9.9.9-test"\n', encoding="utf-8"
    )
    assert get_ramses_tx_version(tmp_path) == "9.9.9-test"


def test_gather_no_device(tmp_path: Path) -> None:
    (tmp_path / "ramses_tx").mkdir()
    (tmp_path / "ramses_tx" / "version.py").write_text(
        '__version__ = "1.2.3"\n', encoding="utf-8"
    )
    m = gather_runtime_versions(
        ramses_port=None,
        gateway_type="auto",
        ramses_rf_src=tmp_path,
        no_device=True,
    )
    assert m["ramses_tx_version"] == "1.2.3"
    assert m["usb_serial_port"] is None
    assert m["stick_firmware_line"] is None
