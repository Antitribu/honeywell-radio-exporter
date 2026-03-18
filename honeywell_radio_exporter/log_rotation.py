"""Rotate log files on process start (same numbering as RotatingFileHandler)."""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def rotate_log_on_startup(path: Path, backup_count: int) -> None:
    """
    If ``path`` exists and is non-empty, rename to ``path.1`` and shift older
    ``path.N`` → ``path.N+1``, dropping ``path.backup_count``.
    """
    if not path.exists():
        return
    try:
        if path.stat().st_size == 0:
            return
    except OSError:
        return

    d, base = path.parent, path.name
    last = d / f"{base}.{backup_count}"
    try:
        if last.exists():
            last.unlink()
        for i in range(backup_count - 1, 0, -1):
            src = d / f"{base}.{i}"
            dst = d / f"{base}.{i + 1}"
            if src.exists():
                src.rename(dst)
        path.rename(d / f"{base}.1")
        logger.info(
            "Rotated previous log to %s (up to %s backups)",
            f"{base}.1",
            backup_count,
        )
    except OSError as e:
        logger.warning("Could not rotate %s: %s", path, e)


def should_rotate_on_startup() -> bool:
    return os.environ.get("LOG_ROTATE_ON_START", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )
