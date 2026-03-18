"""Skip legacy tests that target the old monolithic Prometheus exporter."""

import pytest

_LEGACY_FILES = frozenset(
    {
        "test_exporter.py",
        "test_sample_data_metrics.py",
        "test_zone_names.py",
        "test_device_names.py",
        "test_metrics_validation.py",
    }
)


def pytest_collection_modifyitems(config, items):
    skip = pytest.mark.skip(reason="Legacy: old ramses_prometheus_exporter suite")
    for item in items:
        if item.path.name in _LEGACY_FILES:
            item.add_marker(skip)
