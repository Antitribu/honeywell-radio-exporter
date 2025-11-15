#!/usr/bin/env python3
"""
Entry point for the honeywell_radio_exporter module.

This allows the module to be run directly with:
    python -m honeywell_radio_exporter [options]
"""

import os
import sys
from pathlib import Path

# Add the ramses_rf module to the path
# Check environment variable first, then fall back to default path
ramses_rf_path_env = os.getenv("RAMSES_RF_PATH", "/home/simon/src/3rd-party/ramses_rf/src")
ramses_rf_path = Path(ramses_rf_path_env)
if ramses_rf_path.exists():
    sys.path.insert(0, str(ramses_rf_path))
else:
    # Try the default path as fallback
    default_path = Path("/home/simon/src/3rd-party/ramses_rf/src")
    if default_path.exists():
        sys.path.insert(0, str(default_path))
    else:
        print("Warning: ramses_rf module not found at expected path")
        print(f"Checked: {ramses_rf_path_env}")
        print(
            "Please ensure the ramses_rf module is available or set RAMSES_RF_PATH environment variable"
        )

try:
    from .ramses_prometheus_exporter import main
except ImportError as e:
    print(f"Error importing ramses_prometheus_exporter: {e}")
    print("Make sure all dependencies are installed:")
    print("  pip install -e .")
    sys.exit(1)

if __name__ == "__main__":
    main()
