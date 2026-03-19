"""Insert messages and upsert device rows."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from honeywell_radio_exporter.device_classes import describe_device_class
from honeywell_radio_exporter.fault_log import normalize_fault_event_timestamp
from honeywell_radio_exporter.message_type_descriptions import (
    description_for_message_type,
)

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Repository:
    def __init__(self, conn):
        self.conn = conn

    def _code_name_for_code(self, code: str) -> Optional[str]:
        """
        Best-effort mapping from a RAMSES message `code` to its human `code_name`.

        Used when rebuilding `message_code_counts` after pruning messages (janitor),
        so the UI can keep showing the Type Name column.
        """
        try:
            from ramses_tx.message import CODE_NAMES  # type: ignore[import-not-found]
            from ramses_tx.ramses import CODES_SCHEMA  # type: ignore[import-not-found]
        except Exception:
            return None

        c = (code or "").strip()
        if not c:
            return None

        # ramses_tx often keys by upper-case string codes like "0004"
        for key in (c, c.upper(), c.lower()):
            if key in CODE_NAMES:
                cn = CODE_NAMES.get(key)
                return cn or None

        for code_key, schema in CODES_SCHEMA.items():
            if str(code_key) == c or str(code_key) == c.upper() or str(code_key) == c.lower():
                n = schema.get("name")
                if n:
                    return str(n)

        return None

    def insert_message(
        self,
        *,
        code: str,
        verb: str,
        src_id: str,
        dst_id: str,
        payload: Any,
        raw: Optional[str],
        validation_ok: bool,
        zone: Optional[str] = None,
    ) -> None:
        cur = self.conn.cursor()
        payload_json = None
        if payload is not None:
            try:
                payload_json = json.dumps(payload, default=str)
            except (TypeError, ValueError):
                payload_json = json.dumps({"_repr": str(payload)})
        z = None
        if zone is not None:
            zs = str(zone).strip()
            if zs and zs != "unknown":
                z = zs[:32]
        cur.execute(
            """
            INSERT INTO messages (
                received_at, code, verb, src_id, dst_id, zone,
                payload_json, raw, validation_ok
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                _utcnow(),
                code[:32],
                verb[:8],
                src_id[:32] if src_id else "unknown",
                dst_id[:32] if dst_id else "unknown",
                z,
                payload_json,
                raw[:65535] if raw and len(raw) > 65535 else raw,
                1 if validation_ok else 0,
            ),
        )

    def list_messages_for_api(
        self,
        *,
        code: Optional[str] = None,
        device_id: Optional[str] = None,
        zone: Optional[str] = None,
        limit: int = 25,
        offset: int = 0,
    ) -> Dict[str, Any]:
        lim = max(1, min(100, int(limit)))
        off = max(0, int(offset))
        where: List[str] = []
        args: List[Any] = []
        if code:
            where.append("code = %s")
            args.append(str(code)[:32])
        if zone:
            where.append("zone = %s")
            args.append(str(zone)[:32])
        if device_id:
            did = str(device_id)[:32]
            where.append("(src_id = %s OR dst_id = %s)")
            args.extend([did, did])
        wsql = ("WHERE " + " AND ".join(where)) if where else ""
        cur = self.conn.cursor()
        cur.execute(
            f"""
            SELECT COUNT(*) AS c
            FROM messages
            {wsql}
            """,
            tuple(args),
        )
        total = int(cur.fetchone().get("c") or 0)
        cur.execute(
            f"""
            SELECT id, received_at, code, verb, src_id, dst_id, zone, payload_json
            FROM messages
            {wsql}
            ORDER BY received_at DESC, id DESC
            LIMIT %s OFFSET %s
            """,
            tuple(args + [lim, off]),
        )
        rows = []
        for r in cur.fetchall():
            pj = r.get("payload_json")
            preview = ""
            if pj is not None:
                preview = str(pj)
                if len(preview) > 240:
                    preview = preview[:240] + "…"
            ra = r.get("received_at")
            rows.append(
                {
                    "id": int(r["id"]),
                    "received_at": ra.isoformat() + "Z" if ra else None,
                    "code": r.get("code"),
                    "verb": r.get("verb"),
                    "src_id": r.get("src_id"),
                    "dst_id": r.get("dst_id"),
                    "zone": r.get("zone"),
                    "payload_preview": preview,
                }
            )
        return {"total": total, "limit": lim, "offset": off, "messages": rows}

    def ensure_device_row(self, device_id: str) -> None:
        if not device_id or device_id == "unknown":
            return
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT IGNORE INTO devices (device_id, messages_from, messages_to, acks_from, acks_to)
            VALUES (%s, 0, 0, 0, 0)
            """,
            (device_id,),
        )

    def bump_traffic(self, src_id: str, dst_id: str, verb: str) -> None:
        cur = self.conn.cursor()
        now = _utcnow()
        if src_id and src_id != "unknown":
            self.ensure_device_row(src_id)
            cur.execute(
                "UPDATE devices SET messages_from = messages_from + 1, "
                "last_seen = %s, last_seen_from = %s WHERE device_id = %s",
                (now, now, src_id),
            )
            if verb == "RP":
                cur.execute(
                    "UPDATE devices SET acks_from = acks_from + 1, last_ack = %s "
                    "WHERE device_id = %s",
                    (now, src_id),
                )
        if dst_id and dst_id != "unknown":
            self.ensure_device_row(dst_id)
            cur.execute(
                "UPDATE devices SET messages_to = messages_to + 1, "
                "last_seen = %s, last_seen_to = %s WHERE device_id = %s",
                (now, now, dst_id),
            )
            if verb == "RP":
                cur.execute(
                    "UPDATE devices SET acks_to = acks_to + 1, last_ack = %s "
                    "WHERE device_id = %s",
                    (now, dst_id),
                )

    def update_device_temperature(self, device_id: str, temp: float) -> None:
        self.ensure_device_row(device_id)
        cur = self.conn.cursor()
        cur.execute(
            "UPDATE devices SET temperature = %s, last_seen = %s WHERE device_id = %s",
            (Decimal(str(round(temp, 2))), _utcnow(), device_id),
        )

    def update_device_zone_temp_report(self, device_id: str, report: float) -> None:
        """
        Controller-derived zone temperature *report* (from a `temperature` payload).

        This is intentionally separate from:
        - devices.temperature (device-reported sensed temperature)
        - devices.setpoint (device-reported target setpoint)
        """
        self.ensure_device_row(device_id)
        cur = self.conn.cursor()
        cur.execute(
            "UPDATE devices SET zone_temp_report = %s, last_seen = %s WHERE device_id = %s",
            (Decimal(str(round(report, 2))), _utcnow(), device_id),
        )

    # Backward-compat wrapper (older code paths used this name).
    def update_device_desired_setpoint(self, device_id: str, desired: float) -> None:
        self.update_device_zone_temp_report(device_id, desired)

    def update_device_setpoint(self, device_id: str, sp: float) -> None:
        self.ensure_device_row(device_id)
        cur = self.conn.cursor()
        cur.execute(
            "UPDATE devices SET setpoint = %s, last_seen = %s WHERE device_id = %s",
            (Decimal(str(round(sp, 2))), _utcnow(), device_id),
        )

    def update_device_battery(
        self,
        device_id: str,
        level_pct: Optional[float],
        battery_low: bool,
    ) -> None:
        """1060 device_battery: optional % (0–100), always refresh battery_low flag."""
        self.ensure_device_row(device_id)
        cur = self.conn.cursor()
        low = 1 if battery_low else 0
        if level_pct is not None:
            pct = max(0.0, min(100.0, float(level_pct)))
            cur.execute(
                """
                UPDATE devices SET battery_pct = %s, battery_low = %s, last_seen = %s
                WHERE device_id = %s
                """,
                (Decimal(str(round(pct, 1))), low, _utcnow(), device_id),
            )
        else:
            cur.execute(
                """
                UPDATE devices SET battery_low = %s, last_seen = %s
                WHERE device_id = %s
                """,
                (low, _utcnow(), device_id),
            )

    def update_device_heat_demand(self, device_id: str, demand_pct: float) -> None:
        """heat_demand 0.0–100.0 (% valve open / zone demand from 3150)."""
        self.ensure_device_row(device_id)
        cur = self.conn.cursor()
        pct = max(0.0, min(100.0, float(demand_pct)))
        cur.execute(
            "UPDATE devices SET heat_demand = %s, last_seen = %s WHERE device_id = %s",
            (Decimal(str(round(pct, 2))), _utcnow(), device_id),
        )

    def update_device_window_state(self, device_id: str, state: str) -> None:
        """12B0 window_state: open | closed."""
        if state not in ("open", "closed"):
            return
        self.ensure_device_row(device_id)
        cur = self.conn.cursor()
        cur.execute(
            "UPDATE devices SET window_state = %s, last_seen = %s WHERE device_id = %s",
            (state, _utcnow(), device_id),
        )

    def update_device_name(self, device_id: str, name: str) -> None:
        if not name or name == "unknown":
            return
        self.ensure_device_row(device_id)
        cur = self.conn.cursor()
        cur.execute(
            "UPDATE devices SET name = %s, last_seen = %s WHERE device_id = %s",
            (name[:255], _utcnow(), device_id),
        )

    def update_device_zone(self, device_id: str, zone: str) -> None:
        if not zone or zone == "unknown":
            return
        self.ensure_device_row(device_id)
        cur = self.conn.cursor()
        cur.execute(
            "UPDATE devices SET zone = %s, last_seen = %s WHERE device_id = %s",
            (zone[:255], _utcnow(), device_id),
        )

    def update_devices_zone_batch(self, device_ids: List[str], zone_idx: str) -> None:
        if not device_ids:
            return
        z = zone_idx if zone_idx else "unknown"
        for did in device_ids:
            if did and did != "unknown":
                self.update_device_zone(did, z)

    def upsert_zone(self, zone_idx: str, name: str) -> None:
        if not zone_idx or zone_idx == "unknown" or not name or str(name).strip() == "":
            return
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO zones (zone_idx, name, updated_at)
            VALUES (%s, %s, UTC_TIMESTAMP(6))
            ON DUPLICATE KEY UPDATE
                name = IF(VALUES(name) = zone_idx AND name <> zone_idx, name, VALUES(name)),
                updated_at = UTC_TIMESTAMP(6)
            """,
            (str(zone_idx)[:32], str(name).strip()[:255]),
        )

    def _merge_zone_status(
        self,
        zone_idx: str,
        *,
        following_schedule: Optional[bool] = None,
        setpoint_c: Optional[float] = None,
        temperature_c: Optional[float] = None,
        heat_demand_pct: Optional[float] = None,
    ) -> None:
        if not zone_idx or zone_idx == "unknown":
            return
        zidx = str(zone_idx).strip()[:32]
        # Ensure row exists (name default = zone id).
        self.upsert_zone(zidx, zidx)

        parts: List[str] = []
        args: List[Any] = []

        if following_schedule is not None:
            parts.append("`following_schedule`=%s")
            args.append(1 if following_schedule else 0)
        if setpoint_c is not None:
            parts.append("`setpoint_c`=%s")
            args.append(Decimal(str(round(float(setpoint_c), 2))))
        if temperature_c is not None:
            parts.append("`temperature_c`=%s")
            args.append(Decimal(str(round(float(temperature_c), 2))))
        if heat_demand_pct is not None:
            parts.append("`heat_demand_pct`=%s")
            args.append(Decimal(str(round(float(heat_demand_pct), 2))))

        if not parts:
            return
        parts.append("`updated_at`=%s")
        args.append(_utcnow())
        args.append(zidx)

        cur = self.conn.cursor()
        cur.execute(
            f"UPDATE zones SET {', '.join(parts)} WHERE zone_idx=%s",
            tuple(args),
        )

    def update_zone_following_schedule(
        self,
        zone_idx: str,
        following_schedule: Optional[bool],
        *,
        setpoint_c: Optional[float] = None,
    ) -> None:
        self._merge_zone_status(
            zone_idx,
            following_schedule=following_schedule,
            setpoint_c=setpoint_c,
        )

    def update_zone_setpoint(self, zone_idx: str, setpoint_c: float) -> None:
        self._merge_zone_status(zone_idx, setpoint_c=setpoint_c)

    def update_zone_temperature(self, zone_idx: str, temperature_c: float) -> None:
        self._merge_zone_status(zone_idx, temperature_c=temperature_c)

    def update_zone_heat_demand_pct(
        self, zone_idx: str, heat_demand_pct: float
    ) -> None:
        self._merge_zone_status(zone_idx, heat_demand_pct=heat_demand_pct)

    def bump_zone_message_count(self, zone_idx: str) -> None:
        # Backward-compatible helper: unknown verb counts as "other".
        self.bump_zone_message_counts(zone_idx, verb="OTHER")

    def bump_zone_message_counts(self, zone_idx: str, verb: str) -> None:
        """
        Increment zone message counters split by verb:
        - RQ => rq_message_count
        - RP => rp_message_count
        - everything else => other_message_count
        """
        if not zone_idx or zone_idx == "unknown":
            return
        zidx = str(zone_idx).strip()[:32]
        v = (verb or "").strip().upper()
        rq_inc = 1 if v == "RQ" else 0
        rp_inc = 1 if v == "RP" else 0
        other_inc = 0 if (rq_inc or rp_inc) else 1

        self.upsert_zone(zidx, zidx)
        cur = self.conn.cursor()
        cur.execute(
            """
            UPDATE zones
            SET
                message_count = message_count + 1,
                rq_message_count = rq_message_count + %s,
                rp_message_count = rp_message_count + %s,
                other_message_count = other_message_count + %s,
                updated_at = %s
            WHERE zone_idx = %s
            """,
            (rq_inc, rp_inc, other_inc, _utcnow(), zidx),
        )

    def resync_zone_message_counts_from_messages(self) -> None:
        """
        Recompute zone verb counters from the `messages` table.

        Useful after introducing new columns, so the split counts add up to
        `zones.message_count`.
        """
        cur = self.conn.cursor()
        # mysql REGEXP is case-insensitive for hex patterns, but we keep it simple.
        cur.execute(
            """
            SELECT
                zone,
                SUM(CASE WHEN verb='RQ' THEN 1 ELSE 0 END) AS rq_cnt,
                SUM(CASE WHEN verb='RP' THEN 1 ELSE 0 END) AS rp_cnt,
                COUNT(*) AS total_cnt,
                MAX(received_at) AS last_rcv_at
            FROM messages
            WHERE zone REGEXP '^[0-9A-Fa-f]{2}$'
            GROUP BY zone
            """
        )
        rows = cur.fetchall() or []
        # Update each zone individually to preserve existing zone names.
        for r in rows:
            zidx = r["zone"]
            total = int(r["total_cnt"] or 0)
            rq = int(r["rq_cnt"] or 0)
            rp = int(r["rp_cnt"] or 0)
            oth = max(0, total - rq - rp)
            last_at = r["last_rcv_at"]
            self.upsert_zone(zidx, zidx)
            c2 = self.conn.cursor()
            c2.execute(
                """
                UPDATE zones
                SET message_count=%s,
                    rq_message_count=%s,
                    rp_message_count=%s,
                    other_message_count=%s,
                    updated_at=%s
                WHERE zone_idx=%s
                """,
                (total, rq, rp, oth, last_at, zidx),
            )

    def resync_zone_message_counts_if_out_of_sync(self) -> None:
        """Fast check: if split counts do not add up, resync from messages."""
        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT COUNT(*) AS n
                FROM zones
                WHERE
                    (COALESCE(rq_message_count,0) + COALESCE(rp_message_count,0) + COALESCE(other_message_count,0)) !=
                    COALESCE(message_count,0)
                """
            )
            n = int(cur.fetchone()["n"] or 0)
            if n > 0:
                self.resync_zone_message_counts_from_messages()
        except Exception:
            # If columns don't exist yet or query fails, keep exporter running.
            return

    def bump_message_code_count(self, code: str, code_name: Optional[str]) -> None:
        c = (code or "unknown")[:32]
        cn = (code_name or "").strip()[:128] or None
        cur = self.conn.cursor()
        cur.execute("SELECT code_name FROM message_code_counts WHERE code = %s", (c,))
        row = cur.fetchone()
        if row is None:
            cur.execute(
                """
                INSERT INTO message_code_counts (code, code_name, message_count, last_message_at)
                VALUES (%s, %s, 1, UTC_TIMESTAMP(6))
                """,
                (c, cn),
            )
        else:
            prev_cn = row.get("code_name") if row else None
            new_cn = cn or prev_cn
            cur.execute(
                """
                UPDATE message_code_counts SET
                    message_count = message_count + 1,
                    last_message_at = UTC_TIMESTAMP(6),
                    code_name = %s
                WHERE code = %s
                """,
                (new_cn, c),
            )

    def resync_message_code_counts_from_messages(self) -> None:
        """Rebuild counts from messages (e.g. after janitor prune)."""
        cur = self.conn.cursor()
        cur.execute("DELETE FROM message_code_counts")
        cur.execute(
            """
            SELECT
                code,
                COUNT(*) AS cnt,
                MAX(received_at) AS last_at
            FROM messages
            GROUP BY code
            """
        )
        rows = cur.fetchall() or []
        for r in rows:
            c = r["code"]
            cn = self._code_name_for_code(c)
            # Insert with computed cn (may be None if mapping unavailable)
            cur.execute(
                """
                INSERT INTO message_code_counts (code, code_name, message_count, last_message_at)
                VALUES (%s, %s, %s, %s)
                """,
                (c, cn, int(r["cnt"] or 0), r["last_at"]),
            )

    def list_zones_for_api(self) -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute("""
            SELECT zone_idx, name, updated_at,
                   following_schedule, setpoint_c, temperature_c, heat_demand_pct,
                   message_count, rq_message_count, rp_message_count, other_message_count
            FROM zones ORDER BY zone_idx
            """)
        rows = cur.fetchall()
        out = []
        for r in rows:
            out.append(
                {
                    "zone_idx": r["zone_idx"],
                    "name": r["name"],
                    "updated_at": (
                        r["updated_at"].isoformat() + "Z" if r["updated_at"] else None
                    ),
                    "following_schedule": (
                        None
                        if r.get("following_schedule") is None
                        else bool(r.get("following_schedule"))
                    ),
                    "setpoint_c": (
                        float(r["setpoint_c"]) if r.get("setpoint_c") is not None else None
                    ),
                    "temperature_c": (
                        float(r["temperature_c"])
                        if r.get("temperature_c") is not None
                        else None
                    ),
                    "heat_demand_pct": (
                        float(r["heat_demand_pct"])
                        if r.get("heat_demand_pct") is not None
                        else None
                    ),
                    "message_count": int(r["message_count"] or 0),
                    "rq_message_count": int(r.get("rq_message_count") or 0),
                    "rp_message_count": int(r.get("rp_message_count") or 0),
                    "other_message_count": int(r.get("other_message_count") or 0),
                }
            )
        return out

    def list_recent_messages_by_code(
        self, code: str, limit: int = 25
    ) -> List[Dict[str, Any]]:
        """Last N message rows for a RAMSES code (case-insensitive match)."""
        c = (code or "").strip()[:32]
        if not c:
            return []
        j = self.list_messages_for_api(code=c, limit=limit, offset=0)
        out: List[Dict[str, Any]] = []
        for m in j.get("messages") or []:
            out.append(
                {
                    "received_at": m.get("received_at"),
                    "verb": m.get("verb"),
                    "src_id": m.get("src_id"),
                    "dst_id": m.get("dst_id"),
                    "payload_preview": m.get("payload_preview"),
                }
            )
        return out

    def list_message_code_counts_for_api(self) -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute("""
            SELECT code, code_name, message_count, last_message_at
            FROM message_code_counts
            ORDER BY message_count DESC, code
            """)
        rows = cur.fetchall()
        return [
            {
                "code": r["code"],
                "code_name": r["code_name"],
                "type_description": description_for_message_type(
                    r["code"], r["code_name"]
                ),
                "message_count": int(r["message_count"] or 0),
                "last_message_at": (
                    r["last_message_at"].isoformat() + "Z"
                    if r["last_message_at"]
                    else None
                ),
            }
            for r in rows
        ]

    def janitor_delete_old_messages(self, hours: int) -> int:
        cur = self.conn.cursor()
        cur.execute(
            "DELETE FROM messages WHERE received_at < DATE_SUB(UTC_TIMESTAMP(6), INTERVAL %s HOUR)",
            (hours,),
        )
        return cur.rowcount

    def janitor_delete_stale_devices(self, days: int) -> int:
        cur = self.conn.cursor()
        cur.execute(
            """
            DELETE FROM devices
            WHERE last_seen IS NOT NULL
              AND last_seen < DATE_SUB(UTC_TIMESTAMP(6), INTERVAL %s DAY)
            """,
            (days,),
        )
        return cur.rowcount

    def insert_fault_log_entry(
        self,
        *,
        log_idx: Optional[str],
        event_timestamp: Optional[str],
        fault_state: Optional[str],
        fault_type: Optional[str],
        detail_json: Any,
        device_id: Optional[str],
        src_id: str,
        dst_id: str,
        verb: str,
    ) -> None:
        cur = self.conn.cursor()
        dj = json.dumps(detail_json, default=str) if detail_json else None
        cur.execute(
            """
            INSERT INTO fault_log_entries (
                received_at, log_idx, event_timestamp, fault_state, fault_type,
                detail_json, device_id, src_id, dst_id, verb
            ) VALUES (
                UTC_TIMESTAMP(6), %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            """,
            (
                log_idx,
                event_timestamp,
                fault_state,
                fault_type,
                dj,
                device_id,
                src_id,
                dst_id,
                verb,
            ),
        )

    def list_fault_log_for_api(self, limit: int = 400) -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT id, received_at, log_idx, event_timestamp, fault_state, fault_type,
                   detail_json, device_id, src_id, dst_id, verb
            FROM fault_log_entries
            ORDER BY id DESC
            LIMIT %s
            """,
            (limit,),
        )
        rows = cur.fetchall()
        out = []
        for r in rows:
            det = r["detail_json"]
            if isinstance(det, str):
                try:
                    det = json.loads(det)
                except (TypeError, ValueError):
                    pass
            out.append(
                {
                    "id": r["id"],
                    "received_at": (
                        r["received_at"].isoformat() + "Z" if r["received_at"] else None
                    ),
                    "log_idx": r["log_idx"],
                    "event_timestamp": normalize_fault_event_timestamp(
                        r["event_timestamp"]
                    ),
                    "fault_state": r["fault_state"],
                    "fault_type": r["fault_type"],
                    "detail": det if isinstance(det, list) else det,
                    "device_id": r["device_id"],
                    "src_id": r["src_id"],
                    "dst_id": r["dst_id"],
                    "verb": r["verb"],
                }
            )
        return out

    def janitor_delete_old_fault_entries(self, days: int) -> int:
        cur = self.conn.cursor()
        cur.execute(
            """
            DELETE FROM fault_log_entries
            WHERE received_at < DATE_SUB(UTC_TIMESTAMP(6), INTERVAL %s DAY)
            """,
            (days,),
        )
        return cur.rowcount

    def record_puzzle_version_event(
        self,
        src_id: str,
        dst_id: str,
        engine_version: str,
        parser_version: str,
    ) -> None:
        """Insert when engine/parser pair is new for this gateway (src_id)."""
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT engine_version, parser_version
            FROM puzzle_version_events
            WHERE src_id = %s
            ORDER BY id DESC
            LIMIT 1
            """,
            (src_id,),
        )
        last = cur.fetchone()
        if last:
            le, lp = last["engine_version"] or "", last["parser_version"] or ""
            if le == engine_version and lp == parser_version:
                return
            prev_e, prev_p, is_initial = le or None, lp or None, 0
        else:
            prev_e, prev_p, is_initial = None, None, 1
        cur.execute(
            """
            INSERT INTO puzzle_version_events (
                received_at, src_id, dst_id, engine_version, parser_version,
                prev_engine, prev_parser, is_initial
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                _utcnow(),
                src_id,
                (dst_id or "")[:32],
                engine_version,
                parser_version,
                prev_e,
                prev_p,
                is_initial,
            ),
        )

    def list_puzzle_log_for_api(self, event_limit: int = 80) -> Dict[str, Any]:
        lim = max(1, min(200, int(event_limit)))
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT id, received_at, src_id, dst_id, engine_version, parser_version,
                   prev_engine, prev_parser, is_initial
            FROM puzzle_version_events
            ORDER BY id DESC
            LIMIT %s
            """,
            (lim,),
        )
        events: List[Dict[str, Any]] = []
        for r in cur.fetchall():
            ra = r["received_at"]
            if r["is_initial"]:
                note = "First recording for this gateway"
            else:
                note = (
                    f"{r['prev_engine'] or '—'} / {r['prev_parser'] or '—'} → "
                    f"{r['engine_version'] or '—'} / {r['parser_version'] or '—'}"
                )
            events.append(
                {
                    "id": r["id"],
                    "received_at": ra.isoformat() + "Z" if ra else None,
                    "src_id": r["src_id"],
                    "dst_id": r["dst_id"] or "—",
                    "engine": r["engine_version"],
                    "parser": r["parser_version"],
                    "prev_engine": r["prev_engine"],
                    "prev_parser": r["prev_parser"],
                    "is_initial": bool(r["is_initial"]),
                    "change_note": note,
                }
            )
        cur.execute(
            """
            SELECT p.src_id, p.dst_id, p.engine_version, p.parser_version,
                   p.received_at AS last_change_at,
                   c.cnt AS stored_events,
                   c.first_at AS first_seen
            FROM puzzle_version_events p
            INNER JOIN (
                SELECT src_id, MAX(id) AS mid,
                       COUNT(*) AS cnt,
                       MIN(received_at) AS first_at
                FROM puzzle_version_events
                GROUP BY src_id
            ) c ON p.id = c.mid AND p.src_id = c.src_id
            ORDER BY p.src_id
            """
        )
        gateways: List[Dict[str, Any]] = []
        for r in cur.fetchall():
            la, fa = r["last_change_at"], r["first_seen"]
            cnt = int(r["stored_events"] or 0)
            gateways.append(
                {
                    "src_id": r["src_id"],
                    "dst_id": r["dst_id"] or "—",
                    "engine": r["engine_version"],
                    "parser": r["parser_version"],
                    "stored_events": cnt,
                    "version_changes_observed": max(0, cnt - 1),
                    "first_seen": fa.isoformat() + "Z" if fa else None,
                    "last_change_at": la.isoformat() + "Z" if la else None,
                }
            )
        return {"events": events, "gateways": gateways}

    _BOILER_BOOL = frozenset({"flame_on", "ch_active", "dhw_active", "ch_enabled"})
    _BOILER_DEC = frozenset(
        {"flow_temp_c", "return_temp_c", "target_setpoint_c", "modulation_pct"}
    )

    def merge_boiler_otb(self, otb_id: str, patch: Dict[str, Any]) -> None:
        """Upsert telemetry for OpenTherm bridge 10: or BDR relay boiler 13:."""
        oid = (otb_id or "")[:32]
        if not (oid.startswith("10:") or oid.startswith("13:")):
            return
        cur = self.conn.cursor()
        cur.execute(
            "SELECT otb_device_id FROM boiler_status WHERE otb_device_id=%s", (oid,)
        )
        exists = cur.fetchone() is not None
        now = _utcnow()
        if exists:
            parts: List[str] = []
            args: List[Any] = []
            for k, v in patch.items():
                if k in self._BOILER_BOOL:
                    parts.append(f"`{k}`=%s")
                    args.append(1 if v else 0)
                elif k == "ch_setpoint_c":
                    parts.append("`ch_setpoint_c`=%s")
                    args.append(int(v))
                elif k in self._BOILER_DEC:
                    parts.append(f"`{k}`=%s")
                    fv = float(v)
                    if k == "modulation_pct":
                        args.append(Decimal(str(round(fv, 1))))
                    else:
                        args.append(Decimal(str(round(fv, 2))))
            if not parts:
                return
            parts.append("`updated_at`=%s")
            args.append(now)
            args.append(oid)
            cur.execute(
                f"UPDATE boiler_status SET {', '.join(parts)} WHERE otb_device_id=%s",
                args,
            )
            return
        cols = ["`otb_device_id`", "`updated_at`"]
        vals: List[Any] = [oid, now]
        for k, v in patch.items():
            if k in self._BOILER_BOOL:
                cols.append(f"`{k}`")
                vals.append(1 if v else 0)
            elif k == "ch_setpoint_c":
                cols.append("`ch_setpoint_c`")
                vals.append(int(v))
            elif k in self._BOILER_DEC:
                cols.append(f"`{k}`")
                fv = float(v)
                if k == "modulation_pct":
                    vals.append(Decimal(str(round(fv, 1))))
                else:
                    vals.append(Decimal(str(round(fv, 2))))
        ph = ", ".join(["%s"] * len(vals))
        cur.execute(
            f"INSERT INTO boiler_status ({', '.join(cols)}) VALUES ({ph})",
            vals,
        )

    def list_boiler_status_for_api(self) -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT otb_device_id, updated_at, flame_on, ch_active, dhw_active,
                   ch_enabled, modulation_pct, ch_setpoint_c, flow_temp_c,
                   return_temp_c, target_setpoint_c
            FROM boiler_status
            ORDER BY otb_device_id
            """
        )
        out: List[Dict[str, Any]] = []
        for r in cur.fetchall():
            ua = r["updated_at"]
            bid = r["otb_device_id"]
            out.append(
                {
                    "otb_device_id": bid,
                    "boiler_kind": (
                        "relay" if str(bid).startswith("13:") else "opentherm"
                    ),
                    "updated_at": ua.isoformat() + "Z" if ua else None,
                    "flame_on": (
                        None if r["flame_on"] is None else bool(r["flame_on"])
                    ),
                    "ch_active": (
                        None if r["ch_active"] is None else bool(r["ch_active"])
                    ),
                    "dhw_active": (
                        None if r["dhw_active"] is None else bool(r["dhw_active"])
                    ),
                    "ch_enabled": (
                        None if r["ch_enabled"] is None else bool(r["ch_enabled"])
                    ),
                    "modulation_pct": (
                        float(r["modulation_pct"])
                        if r["modulation_pct"] is not None
                        else None
                    ),
                    "ch_setpoint_c": r["ch_setpoint_c"],
                    "flow_temp_c": (
                        float(r["flow_temp_c"])
                        if r["flow_temp_c"] is not None
                        else None
                    ),
                    "return_temp_c": (
                        float(r["return_temp_c"])
                        if r["return_temp_c"] is not None
                        else None
                    ),
                    "target_setpoint_c": (
                        float(r["target_setpoint_c"])
                        if r["target_setpoint_c"] is not None
                        else None
                    ),
                }
            )
        return out

    def merge_dhw_status(self, dhw_idx: str, patch: Dict[str, Any]) -> None:
        """Upsert DHW (hot water) status keyed by dhw_idx (usually '00')."""
        idx = (dhw_idx or "").strip()[:8]
        if not idx:
            return
        cur = self.conn.cursor()
        cur.execute("SELECT dhw_idx FROM dhw_status WHERE dhw_idx=%s", (idx,))
        exists = cur.fetchone() is not None
        now = _utcnow()

        def dec2(v: Any) -> Any:
            try:
                return Decimal(str(round(float(v), 2)))
            except Exception:
                return None

        cols: List[str] = []
        vals: List[Any] = []
        for k, v in patch.items():
            if k == "controller_id":
                cols.append("`controller_id`=%s")
                vals.append((str(v)[:32] if v else None))
            elif k == "mode":
                cols.append("`mode`=%s")
                vals.append((str(v)[:64] if v is not None else None))
            elif k == "active":
                cols.append("`active`=%s")
                vals.append(None if v is None else (1 if bool(v) else 0))
            elif k == "temperature_c":
                dv = dec2(v)
                if dv is not None:
                    cols.append("`temperature_c`=%s")
                    vals.append(dv)
            elif k == "setpoint_c":
                dv = dec2(v)
                if dv is not None:
                    cols.append("`setpoint_c`=%s")
                    vals.append(dv)
            elif k == "overrun":
                try:
                    cols.append("`overrun`=%s")
                    vals.append(int(v))
                except Exception:
                    pass
            elif k == "differential_c":
                dv = dec2(v)
                if dv is not None:
                    cols.append("`differential_c`=%s")
                    vals.append(dv)

        if not cols:
            return

        if exists:
            cols.append("`updated_at`=%s")
            vals.append(now)
            vals.append(idx)
            cur.execute(
                f"UPDATE dhw_status SET {', '.join(cols)} WHERE dhw_idx=%s",
                vals,
            )
            return

        # insert
        ins_cols = ["`dhw_idx`", "`updated_at`"]
        ins_vals: List[Any] = [idx, now]
        for stmt, v in zip(cols, vals):
            # stmt looks like `col`=%s
            c = stmt.split("=", 1)[0]
            ins_cols.append(c)
            ins_vals.append(v)
        ph = ", ".join(["%s"] * len(ins_vals))
        cur.execute(
            f"INSERT INTO dhw_status ({', '.join(ins_cols)}) VALUES ({ph})",
            ins_vals,
        )

    def list_dhw_status_for_api(self) -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT dhw_idx, updated_at, controller_id, mode, active,
                   temperature_c, setpoint_c, overrun, differential_c
            FROM dhw_status
            ORDER BY dhw_idx
            """
        )
        out: List[Dict[str, Any]] = []
        for r in cur.fetchall():
            ua = r["updated_at"]
            out.append(
                {
                    "dhw_idx": r["dhw_idx"],
                    "updated_at": ua.isoformat() + "Z" if ua else None,
                    "controller_id": r.get("controller_id"),
                    "mode": r.get("mode"),
                    "active": None if r.get("active") is None else bool(r.get("active")),
                    "temperature_c": (
                        float(r["temperature_c"])
                        if r.get("temperature_c") is not None
                        else None
                    ),
                    "setpoint_c": (
                        float(r["setpoint_c"]) if r.get("setpoint_c") is not None else None
                    ),
                    "overrun": r.get("overrun"),
                    "differential_c": (
                        float(r["differential_c"])
                        if r.get("differential_c") is not None
                        else None
                    ),
                }
            )
        return out

    def list_devices_for_api(self) -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        # `devices.zone` is historically written as either a zone label or a zone_idx.
        # We normalize both fields using a LEFT JOIN to the `zones` table so the UI can
        # always display the human-readable zone name.
        cur.execute("""
            SELECT
                d.device_id,
                d.name,
                d.zone AS zone_raw,
                d.type,
                d.last_seen,
                d.last_seen_from,
                d.last_seen_to,
                d.last_ack,
                d.zone_temp_report,
                d.messages_from,
                d.messages_to,
                d.acks_from,
                d.acks_to,
                d.setpoint,
                d.temperature,
                d.heat_demand,
                d.battery_pct,
                d.battery_low,
                d.window_state,
                z.zone_idx AS matched_zone_idx,
                z.name AS matched_zone_name
            FROM devices d
            LEFT JOIN zones z
              ON z.zone_idx = d.zone OR z.name = d.zone
            ORDER BY d.device_id
            """)
        rows = cur.fetchall()
        out = []
        for r in rows:
            mf, mt = int(r["messages_from"] or 0), int(r["messages_to"] or 0)
            dch, dcdesc = describe_device_class(r["device_id"])
            zone_raw = r.get("zone_raw") or "unknown"
            zone_idx = r.get("matched_zone_idx") or zone_raw
            zone_name = r.get("matched_zone_name") or zone_raw
            out.append(
                {
                    "device_id": r["device_id"],
                    "device_class": dch.upper() if dch else None,
                    "device_class_description": dcdesc,
                    "name": r["name"] or "unknown",
                    "zone_idx": zone_idx,
                    "zone_name": zone_name,
                    "last_seen_iso": (
                        r["last_seen"].isoformat() + "Z" if r["last_seen"] else None
                    ),
                    "last_seen_from_iso": (
                        r["last_seen_from"].isoformat() + "Z"
                        if r.get("last_seen_from")
                        else None
                    ),
                    "last_seen_to_iso": (
                        r["last_seen_to"].isoformat() + "Z"
                        if r.get("last_seen_to")
                        else None
                    ),
                    "last_ack_iso": (
                        r["last_ack"].isoformat() + "Z" if r.get("last_ack") else None
                    ),
                    "zone_temp_report_c": (
                        float(r["zone_temp_report"])
                        if r.get("zone_temp_report") is not None
                        else None
                    ),
                    "messages_from": mf,
                    "messages_to": mt,
                    "acks_from": int(r["acks_from"] or 0),
                    "acks_to": int(r["acks_to"] or 0),
                    "messages_as_source": mf,
                    "is_placeholder": mf == 0 and mt > 0 and not r["name"],
                    "temperature_c": (
                        float(r["temperature"])
                        if r["temperature"] is not None
                        else None
                    ),
                    "setpoint_c": (
                        float(r["setpoint"]) if r["setpoint"] is not None else None
                    ),
                    "heat_demand_pct": (
                        float(r["heat_demand"])
                        if r.get("heat_demand") is not None
                        else None
                    ),
                    "battery_pct": (
                        float(r["battery_pct"])
                        if r.get("battery_pct") is not None
                        else None
                    ),
                    "battery_low": bool(r.get("battery_low")),
                    "window_state": (r.get("window_state") or None),
                    "device_type": r["type"],
                    "slug": None,
                    "alias": None,
                    "on_gateway": False,
                }
            )
        return out

    def metrics_snapshot(self) -> Dict[str, Any]:
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) AS c FROM messages")
        msg_count = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) AS c FROM devices")
        dev_count = cur.fetchone()["c"]
        cur.execute("SELECT MAX(received_at) AS m FROM messages")
        row = cur.fetchone()
        last_msg = row["m"]
        return {
            "messages_total_approx": msg_count,
            "devices_total": dev_count,
            "last_message_time": last_msg.timestamp() if last_msg else None,
        }
