#!/usr/bin/env python3
"""Tests for app entry."""

import sys
from unittest.mock import MagicMock, patch

import pytest


def test_main_module_import():
    from honeywell_radio_exporter import __main__

    assert __main__ is not None


def test_app_main_starts_http_only():
    creds = {
        "host": "127.0.0.1",
        "port": 3306,
        "user": "u",
        "password": "p",
        "database": "d",
        "charset": "utf8mb4",
    }
    mock_thread = MagicMock()
    mock_httpd = MagicMock()
    mock_httpd.serve_forever.side_effect = KeyboardInterrupt

    with patch("honeywell_radio_exporter.app.load_mysql_creds", return_value=creds):
        with patch("honeywell_radio_exporter.app.ensure_database_exists"):
            with patch("honeywell_radio_exporter.app.run_migrations"):
                with patch(
                    "honeywell_radio_exporter.app.threading.Thread",
                    return_value=mock_thread,
                ):
                    with patch(
                        "honeywell_radio_exporter.app.start_http_server",
                        return_value=mock_httpd,
                    ):
                        with patch.object(
                            sys,
                            "argv",
                            ["honeywell-radio-exporter", "--no-device"],
                        ):
                            from honeywell_radio_exporter.app import main

                            main()
    mock_httpd.serve_forever.assert_called_once()
    assert mock_thread.start.call_count >= 2
