"""Periodic DB cleanup thread."""

from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING, Any, Dict, Optional

from honeywell_radio_exporter import config
from honeywell_radio_exporter.db.connection import connect

if TYPE_CHECKING:
    from honeywell_radio_exporter.live_events import LiveNotifier
from honeywell_radio_exporter.db.repository import Repository

logger = logging.getLogger(__name__)


def run_janitor(
    creds: Dict[str, Any],
    stop_event: threading.Event,
    interval_sec: int,
    message_hours: int,
    device_days: int,
    live_events: Optional["LiveNotifier"] = None,
) -> None:
    while not stop_event.is_set():
        for _ in range(interval_sec):
            if stop_event.is_set():
                return
            time.sleep(1)
        try:
            conn = connect(creds)
            repo = Repository(conn)
            n1 = repo.janitor_delete_old_messages(message_hours)
            if n1:
                repo.resync_message_code_counts_from_messages()
            n2 = repo.janitor_delete_stale_devices(device_days)
            n3 = repo.janitor_delete_old_fault_entries(config.FAULT_LOG_RETENTION_DAYS)
            conn.commit()
            conn.close()
            if n1 or n2 or n3:
                logger.info(
                    "Janitor: %s msgs, %s devices, %s fault rows",
                    n1,
                    n2,
                    n3,
                )
                if live_events is not None:
                    live_events.notify()
        except Exception as e:
            logger.exception("Janitor error: %s", e)
