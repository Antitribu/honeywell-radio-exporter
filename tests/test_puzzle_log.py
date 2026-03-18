"""puzzle version tracking."""

from unittest.mock import MagicMock

from honeywell_radio_exporter.puzzle_log import try_record_puzzle_version


def test_try_record_skips_non_puzzle():
    repo = MagicMock()
    try_record_puzzle_version(repo, {"code": "30C9", "payload": {"engine": "x"}})
    repo.record_puzzle_version_event.assert_not_called()


def test_try_record_skips_without_engine_parser():
    repo = MagicMock()
    try_record_puzzle_version(
        repo,
        {
            "code": "7FFF",
            "code_name": "puzzle_packet",
            "src_id": "18:147744",
            "payload": {"datetime": "x"},
        },
    )
    repo.record_puzzle_version_event.assert_not_called()


def test_try_record_calls_with_versions():
    repo = MagicMock()
    try_record_puzzle_version(
        repo,
        {
            "code": "7FFF",
            "code_name": "puzzle_packet",
            "src_id": "18:147744",
            "dst_id": "63:262142",
            "payload": {"engine": "v0.51.4", "parser": "v0.51.4"},
        },
    )
    repo.record_puzzle_version_event.assert_called_once_with(
        src_id="18:147744",
        dst_id="63:262142",
        engine_version="v0.51.4",
        parser_version="v0.51.4",
    )
