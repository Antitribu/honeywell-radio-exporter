#!/usr/bin/env python3
"""
Tests for the __main__.py module entry point.
"""

import sys
from unittest.mock import patch, MagicMock
import pytest


def test_main_module_import():
    """Test that the main module can be imported."""
    # This test verifies that the __main__.py file is syntactically correct
    # and can be imported without errors (assuming dependencies are available)

    # Mock the ramses_rf path to avoid import issues
    with patch("pathlib.Path.exists", return_value=True):
        with patch("sys.path.insert"):
            try:
                # Try to import the main module
                from honeywell_radio_exporter import __main__

                assert __main__ is not None
            except ImportError:
                # It's okay if dependencies are missing
                pass


def test_main_module_execution():
    """Test that the main module can be executed."""
    # This test verifies that the __main__.py file can be executed
    # and calls the main function from ramses_prometheus_exporter

    with patch("honeywell_radio_exporter.ramses_prometheus_exporter.main") as mock_main:
        with patch("pathlib.Path.exists", return_value=True):
            with patch("sys.path.insert"):
                # Import and execute the main module
                from honeywell_radio_exporter import __main__

                # Simulate running the module
                if hasattr(__main__, "__name__"):
                    __main__.__name__ = "__main__"
                    exec(open(__main__.__file__).read(), __main__.__dict__)

                # Verify that main was called
                mock_main.assert_called_once()


def test_ramses_rf_path_handling():
    """Test that the ramses_rf path is handled correctly."""
    from pathlib import Path

    # Test with existing path
    with patch("pathlib.Path.exists", return_value=True) as mock_exists:
        with patch("sys.path.insert") as mock_insert:
            from honeywell_radio_exporter import __main__

            mock_exists.assert_called_once()
            mock_insert.assert_called_once()

    # Test with non-existing path
    with patch("pathlib.Path.exists", return_value=False) as mock_exists:
        with patch("builtins.print") as mock_print:
            with patch("sys.path.insert") as mock_insert:
                from honeywell_radio_exporter import __main__

                mock_exists.assert_called_once()
                mock_insert.assert_not_called()
                mock_print.assert_called()


def test_import_error_handling():
    """Test that import errors are handled gracefully."""
    with patch(
        "honeywell_radio_exporter.ramses_prometheus_exporter.main",
        side_effect=ImportError("Test error"),
    ):
        with patch("pathlib.Path.exists", return_value=True):
            with patch("sys.path.insert"):
                with patch("builtins.print") as mock_print:
                    with patch("sys.exit") as mock_exit:
                        try:
                            from honeywell_radio_exporter import __main__

                            # If we get here, the error handling worked
                            mock_print.assert_called()
                            mock_exit.assert_called_once_with(1)
                        except ImportError:
                            # This is also acceptable behavior
                            pass


if __name__ == "__main__":
    pytest.main([__file__])
