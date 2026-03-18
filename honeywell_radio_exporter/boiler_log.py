"""Track boiler telemetry: OpenTherm bridge (10:) and BDR relay (13:)."""

from __future__ import annotations

from typing import Any, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from honeywell_radio_exporter.db.repository import Repository


_BDR_IDS_CACHE: list[str] | None = None


def _get_bdr_ids(repo: "Repository") -> list[str]:
    """
    Return known BDR relay device ids (13:...). Cached because relay_demand
    traffic can be frequent.
    """
    global _BDR_IDS_CACHE
    if _BDR_IDS_CACHE is not None:
        return _BDR_IDS_CACHE
    cur = repo.conn.cursor()
    cur.execute(
        "SELECT device_id FROM devices WHERE device_id LIKE '13:%' ORDER BY last_seen DESC"
    )
    rows = cur.fetchall() or []
    out: list[str] = []
    for r in rows:
        did = r.get("device_id")
        if did:
            out.append(str(did)[:32])
    _BDR_IDS_CACHE = out
    return out


def try_record_boiler_telemetry(repo: "Repository", item: Dict[str, Any]) -> None:
    """
    OpenTherm (10:): 3EF0, 3200, 3210, 22D9 as before.

    Relay BDR (13:): no flow/return temps. Heat call / TPI duty from:
    - RP (or I) 0008 relay_demand — demand 0.0–1.0 → modulation_pct
    - I 3EF0 short payload — modulation_level 0/1 (00/FF vs C8/FF style)
    """
    code = str(item.get("code") or "").strip().upper()
    cn = (item.get("code_name") or "").strip().lower()
    src = str(item.get("src_id") or "").strip()
    payload = item.get("payload")
    if not isinstance(payload, dict):
        return

    # relay_demand (0008): in some setups the controller sends it (src=01:...),
    # while the BDR only issues RQ. We still want to populate boiler_status.
    if code == "0008" or cn == "relay_demand":
        rd = payload.get("relay_demand")
        if rd is not None and not isinstance(rd, str):
            try:
                pct = round(float(rd) * 100.0, 2)
                pct = max(0.0, min(100.0, pct))
                if src.startswith("13:"):
                    target_ids = [src]
                else:
                    target_ids = _get_bdr_ids(repo)
                for bid in target_ids:
                    repo.merge_boiler_otb(
                        bid,
                        {
                            "modulation_pct": pct,
                            "ch_active": pct > 0.0,
                        },
                    )
            except (TypeError, ValueError):
                pass
        return

    if src.startswith("13:"):

        if code == "3EF0" or cn == "actuator_state":
            patch: Dict[str, Any] = {}
            mod = payload.get("modulation_level")
            if mod is not None and not isinstance(mod, str):
                try:
                    pct = round(float(mod) * 100.0, 1)
                    pct = max(0.0, min(100.0, pct))
                    patch["modulation_pct"] = pct
                    patch["ch_active"] = pct > 0.0
                except (TypeError, ValueError):
                    pass
            if "flame_on" in payload:
                patch["flame_on"] = bool(payload["flame_on"])
            if "ch_active" in payload and "ch_active" not in patch:
                patch["ch_active"] = bool(payload["ch_active"])
            if "dhw_active" in payload:
                patch["dhw_active"] = bool(payload["dhw_active"])
            if "ch_enabled" in payload:
                patch["ch_enabled"] = bool(payload["ch_enabled"])
            if payload.get("ch_setpoint") is not None:
                try:
                    patch["ch_setpoint_c"] = int(payload["ch_setpoint"])
                except (TypeError, ValueError):
                    pass
            if patch:
                repo.merge_boiler_otb(src, patch)
        return

    if not src.startswith("10:"):
        return

    if code == "3200" or cn == "boiler_output":
        t = payload.get("temperature")
        if t is not None:
            try:
                repo.merge_boiler_otb(src, {"flow_temp_c": float(t)})
            except (TypeError, ValueError):
                pass
        return

    if code == "3210" or cn == "boiler_return":
        t = payload.get("temperature")
        if t is not None:
            try:
                repo.merge_boiler_otb(src, {"return_temp_c": float(t)})
            except (TypeError, ValueError):
                pass
        return

    if code == "22D9" and payload.get("setpoint") is not None:
        try:
            repo.merge_boiler_otb(src, {"target_setpoint_c": float(payload["setpoint"])})
        except (TypeError, ValueError):
            pass
        return

    if code == "3EF0" or cn == "actuator_state":
        if "flame_on" not in payload and "ch_active" not in payload:
            return
        patch_otb: Dict[str, Any] = {}
        if "flame_on" in payload:
            patch_otb["flame_on"] = bool(payload["flame_on"])
        if "ch_active" in payload:
            patch_otb["ch_active"] = bool(payload["ch_active"])
        if "dhw_active" in payload:
            patch_otb["dhw_active"] = bool(payload["dhw_active"])
        if "ch_enabled" in payload:
            patch_otb["ch_enabled"] = bool(payload["ch_enabled"])
        if payload.get("ch_setpoint") is not None:
            try:
                patch_otb["ch_setpoint_c"] = int(payload["ch_setpoint"])
            except (TypeError, ValueError):
                pass
        mod = payload.get("modulation_level")
        if mod is not None and not isinstance(mod, str):
            try:
                patch_otb["modulation_pct"] = round(float(mod) * 100.0, 1)
            except (TypeError, ValueError):
                pass
        if patch_otb:
            repo.merge_boiler_otb(src, patch_otb)
