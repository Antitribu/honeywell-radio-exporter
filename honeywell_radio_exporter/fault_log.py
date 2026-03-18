"""Persist Evohome system_fault (RAMSES 0418) log entries from parsed payloads."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from honeywell_radio_exporter.db.repository import Repository

_DEV_ID_RE = re.compile(r"^[0-9]{2}:[0-9A-Fa-f]{6}$")
# ramses_rf hex_to_dts uses 2-digit year; expand for display/storage clarity
_TS_4Y_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
_TS_2Y_PREFIX = re.compile(r"^(\d{2}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})")


def normalize_fault_event_timestamp(ts: Optional[str]) -> Optional[str]:
    """
    Evohome fault log timestamps from the RF stack are yy-mm-ddTHH:MM:SS.
    Return the same instant as yyyy-mm-ddTHH:MM:SS. Pass through if already
    4-digit year or unrecognized.
    """
    if ts is None:
        return None
    if not isinstance(ts, str):
        return ts
    s = ts.strip()
    if not s:
        return None
    if _TS_4Y_PREFIX.match(s):
        return s
    m = _TS_2Y_PREFIX.match(s)
    if not m:
        return s
    core = m.group(1)
    try:
        d = datetime.strptime(core, "%y-%m-%dT%H:%M:%S")
    except ValueError:
        return s
    expanded = d.strftime("%Y-%m-%dT%H:%M:%S")
    return expanded + s[len(core) :]


def try_record_fault_log(repo: "Repository", item: Dict[str, Any]) -> None:
    """
    When gateway parses 0418 RP/I with a non-null log_entry tuple/list,
    store one row (RQ poll requests are ignored).
    """
    verb = (item.get("verb") or "").strip().upper()
    if verb == "RQ":
        return

    code = str(item.get("code") or "").strip()
    code_name = (item.get("code_name") or "").strip().lower()
    if code != "0418" and code_name != "system_fault":
        return

    payload = item.get("payload")
    if not isinstance(payload, dict):
        return

    le = payload.get("log_entry")
    if le is None or isinstance(le, dict):
        return
    if not isinstance(le, (list, tuple)) or len(le) < 3:
        return

    raw_ts = str(le[0]).strip()[:64] if le[0] is not None else None
    event_ts = normalize_fault_event_timestamp(raw_ts) if raw_ts else None
    fault_state = str(le[1]).strip()[:32] if len(le) > 1 and le[1] is not None else None
    fault_type = str(le[2]).strip()[:64] if len(le) > 2 and le[2] is not None else None
    detail = [x for x in le[3:] if x is not None]

    device_id = None
    for x in le:
        if isinstance(x, str) and _DEV_ID_RE.match(x.strip()):
            device_id = x.strip()[:32]
            break

    log_idx = payload.get("log_idx")
    li = (
        str(log_idx).strip()[:8]
        if log_idx is not None and str(log_idx).strip()
        else None
    )

    repo.insert_fault_log_entry(
        log_idx=li,
        event_timestamp=event_ts or None,
        fault_state=fault_state or None,
        fault_type=fault_type or None,
        detail_json=detail,
        device_id=device_id,
        src_id=str(item.get("src_id") or "")[:32],
        dst_id=str(item.get("dst_id") or "")[:32],
        verb=verb[:8] or "?",
    )
