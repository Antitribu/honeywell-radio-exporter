"""Signals HTTP clients when the consumer commits new DB rows (for UI refresh)."""

from __future__ import annotations

import threading
import time
from typing import Optional


class LiveNotifier:
    """Thread-safe counter bumped after each successful message commit."""

    def __init__(self) -> None:
        self._cond = threading.Condition()
        self._seq = 0

    def notify(self) -> None:
        with self._cond:
            self._seq += 1
            self._cond.notify_all()

    def current_seq(self) -> int:
        with self._cond:
            return self._seq

    def wait_after(self, seq: int, timeout: float) -> int:
        """Wait until _seq > seq or timeout seconds. Returns latest seq."""
        with self._cond:
            deadline = time.monotonic() + timeout
            while self._seq <= seq:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return self._seq
                self._cond.wait(timeout=min(remaining, 30.0))
            return self._seq


_noop = LiveNotifier()


def optional_notifier(x: Optional[LiveNotifier]) -> LiveNotifier:
    return x if x is not None else _noop
