"""Keep the last N WARNING+ log records for the UI (in-memory, per process)."""

from __future__ import annotations

import logging
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List

_MAX = 50
_buffer: Deque[Dict[str, Any]] = deque(maxlen=_MAX)
_lock = threading.Lock()


class WarningBufferHandler(logging.Handler):
    """Records WARNING, ERROR, CRITICAL to a fixed-size thread-safe buffer."""

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = record.getMessage()
        except Exception:
            msg = "<bad log record>"
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        if record.msecs:
            ts = f"{ts}.{int(record.msecs):03d}"
        entry = {
            "time_utc": ts + "Z",
            "logger": record.name,
            "level": record.levelname,
            "message": msg,
        }
        with _lock:
            _buffer.append(entry)


def get_recent_warnings() -> List[Dict[str, Any]]:
    """Newest first (up to 50)."""
    with _lock:
        return list(reversed(_buffer))


def attach_warning_buffer_handler() -> None:
    root = logging.getLogger()
    if any(isinstance(h, WarningBufferHandler) for h in root.handlers):
        return
    root.addHandler(WarningBufferHandler())
