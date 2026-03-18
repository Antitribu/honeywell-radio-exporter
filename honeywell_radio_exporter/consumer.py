"""Consumer thread: queue -> validate -> MySQL."""

from __future__ import annotations

import logging
import queue
import threading
import re
from typing import TYPE_CHECKING, Any, Dict, Optional

from honeywell_radio_exporter.db.connection import connect

if TYPE_CHECKING:
    from honeywell_radio_exporter.live_events import LiveNotifier
from honeywell_radio_exporter.db.repository import Repository
from honeywell_radio_exporter.message_processor import ZoneState, apply_payload
from honeywell_radio_exporter.boiler_log import try_record_boiler_telemetry
from honeywell_radio_exporter.dhw_log import try_record_dhw_status
from honeywell_radio_exporter.puzzle_log import try_record_puzzle_version
from honeywell_radio_exporter.validator import validate_message

logger = logging.getLogger(__name__)


def _extract_zone(item: Dict[str, Any]) -> Optional[str]:
    payload = item.get("payload")
    if isinstance(payload, dict):
        # Only treat values that represent an actual zone index as a zone.
        # `domain_id` shows up in some non-zone packets (e.g. tpi_params / relay_demand)
        # and would otherwise create bogus `zones` rows.
        for k in ("zone_idx", "ufx_idx"):
            v = payload.get(k)
            if v is None:
                continue
            s = str(v).strip()
            if s:
                return s[:32]
    return None


def _looks_like_zone_idx(z: str) -> bool:
    """
    Keep zone table rows sane: most zone_idx values are short hex (e.g. '00', '0A').
    """
    return bool(re.fullmatch(r"[0-9A-Fa-f]{2}", str(z).strip()))


def run_consumer(
    creds: Dict[str, Any],
    msg_queue: "queue.Queue[Dict[str, Any]]",
    stop_event: threading.Event,
    live_events: Optional["LiveNotifier"] = None,
) -> None:
    state = ZoneState()
    while not stop_event.is_set():
        try:
            item = msg_queue.get(timeout=0.5)
        except queue.Empty:
            continue
        conn = None
        try:
            conn = connect(creds)
            repo = Repository(conn)
            vr = validate_message(
                code=item.get("code") or "",
                verb=item.get("verb") or "",
                payload=item.get("payload"),
                code_name_hint=item.get("code_name"),
            )
            if not vr.ok:
                logger.warning(
                    "Validation issues %s: %s",
                    item.get("raw", "")[:120],
                    vr.errors,
                )
            repo.insert_message(
                code=item.get("code") or "unknown",
                verb=item.get("verb") or "unknown",
                src_id=item.get("src_id") or "unknown",
                dst_id=item.get("dst_id") or "unknown",
                payload=item.get("payload"),
                raw=item.get("raw"),
                validation_ok=vr.ok,
                zone=(zone := _extract_zone(item)),
            )

            if zone and _looks_like_zone_idx(zone):
                repo.bump_zone_message_counts(zone, item.get("verb") or "")
            repo.bump_message_code_count(
                item.get("code") or "unknown",
                item.get("code_name"),
            )
            repo.bump_traffic(
                item.get("src_id") or "unknown",
                item.get("dst_id") or "unknown",
                item.get("verb") or "",
            )
            apply_payload(repo, item, state)
            try_record_puzzle_version(repo, item)
            try_record_boiler_telemetry(repo, item)
            try_record_dhw_status(repo, item)
            conn.commit()
            if live_events is not None:
                live_events.notify()
        except Exception as e:
            logger.exception("Consumer error: %s", e)
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
