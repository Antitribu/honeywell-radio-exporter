"""Paths and runtime defaults for honeywell_radio_exporter."""

import os
from pathlib import Path

# Package parent = project root when installed editable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = PROJECT_ROOT / "logs"
RAW_MESSAGES_LOG_DIR = LOGS_DIR / "raw_messages"
MESSAGES_LOG = LOGS_DIR / "messages.log"
MYSQL_CREDS_PATH = PROJECT_ROOT / ".mysql_creds"

# Raw message rotation: 100 MB × 5 files (per project_description)
RAW_LOG_MAX_BYTES = 100 * 1024 * 1024
RAW_LOG_BACKUP_COUNT = 5

MESSAGE_QUEUE_MAXSIZE = 10_000
JANITOR_INTERVAL_SEC = 300
MESSAGE_RETENTION_HOURS = 24
DEVICE_STALE_DAYS = 28
FAULT_LOG_RETENTION_DAYS = 90

HTTP_PORT = 8000
# "" or "0.0.0.0" = all interfaces (LAN access). Use "127.0.0.1" to block remote clients.
HTTP_BIND = os.environ.get("HTTP_BIND", "0.0.0.0")
DEFAULT_RAMSES_PORT = "/dev/ttyACM0"
# ramses_rf Python package root (contains ramses_tx/). Override with RAMSES_RF_PATH.
RAMSES_RF_SRC = Path(
    os.environ.get("RAMSES_RF_PATH", "/home/simon/src/3rd-party/ramses_rf/src")
)
