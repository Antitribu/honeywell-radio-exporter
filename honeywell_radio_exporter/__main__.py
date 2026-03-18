#!/usr/bin/env python3
"""python -m honeywell_radio_exporter"""

import sys

try:
    from honeywell_radio_exporter.app import main
except ImportError as e:
    print(f"Error importing app: {e}")
    print("Install dependencies: pip install -e .")
    sys.exit(1)

if __name__ == "__main__":
    main()
