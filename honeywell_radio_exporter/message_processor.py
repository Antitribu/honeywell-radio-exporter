"""Apply payload-derived updates to devices (zone names, temps, setpoints)."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from honeywell_radio_exporter.db.repository import Repository
from honeywell_radio_exporter.fault_log import try_record_fault_log

logger = logging.getLogger(__name__)


def _heat_demand_to_pct(hd: Any) -> Optional[float]:
    if hd is None or isinstance(hd, str):
        return None
    try:
        return round(float(hd) * 100.0, 2)
    except (TypeError, ValueError):
        return None


def _distribute_setpoint_to_zone(
    repo: Repository, state: ZoneState, zone_idx: str, sp: float
) -> int:
    """Apply setpoint to all devices mapped into zone (000C). Returns count updated."""
    n = 0
    for role_devs in state.zone_devices.get(zone_idx, {}).values():
        for did in role_devs:
            if did and did != "unknown":
                repo.update_device_setpoint(did, sp)
                n += 1
    return n


def _distribute_zone_temp_report_to_zone(
    repo: Repository, state: ZoneState, zone_idx: str, report: float
) -> int:
    """Apply controller-derived zone temperature report to all devices in this zone."""
    n = 0
    for role_devs in state.zone_devices.get(zone_idx, {}).values():
        for did in role_devs:
            if did and did != "unknown":
                repo.update_device_zone_temp_report(did, report)
                n += 1
    return n


def _is_actuator_destination(dst: str) -> bool:
    """True if dst looks like a field device, not controller/gateway."""
    if not dst or dst == "unknown":
        return False
    if dst.startswith(("01:", "18:", "63:")):
        return False
    return ":" in dst


def _apply_heat_demand(
    repo: Repository, state: ZoneState, src: str, payload: Any
) -> None:
    """3150 heat_demand: TRV reports dict; controller may broadcast list per zone."""
    if isinstance(payload, list):
        for ent in payload:
            if not isinstance(ent, dict):
                continue
            pct = _heat_demand_to_pct(ent.get("heat_demand"))
            if pct is None:
                continue
            zidx = ent.get("zone_idx") or ent.get("ufx_idx")
            if zidx is None:
                continue
            zkey = str(zidx)
            repo.update_zone_heat_demand_pct(zkey, pct)
            for role_devs in state.zone_devices.get(zkey, {}).values():
                for did in role_devs:
                    if did and did != "unknown":
                        repo.update_device_heat_demand(did, pct)
    elif isinstance(payload, dict):
        pct = _heat_demand_to_pct(payload.get("heat_demand"))
        if pct is not None and src and src != "unknown":
            zidx = payload.get("zone_idx") or payload.get("ufx_idx")
            if zidx is not None:
                repo.update_zone_heat_demand_pct(str(zidx), pct)
            else:
                # If device reported heat_demand without zone_idx, map device->zone_idx
                # (not device->zone label) before writing to the `zones` table.
                zidx = state.zone_idx_for_device(src)
                if zidx != "unknown":
                    repo.update_zone_heat_demand_pct(zidx, pct)
            repo.update_device_heat_demand(src, pct)


class ZoneState:
    def __init__(self) -> None:
        self.zone_names: Dict[str, str] = {}
        self.zone_devices: Dict[str, Dict[str, List[str]]] = {}
        # Cache controller-derived per-zone temperature reports.
        # Useful because some systems send temperature packets before zone_devices
        # is known; we apply once devices for that zone arrive.
        self.zone_temp_reports: Dict[str, float] = {}

    def zone_label(self, zone_idx: str) -> str:
        if not zone_idx or zone_idx == "unknown":
            return "unknown"
        return self.zone_names.get(zone_idx, zone_idx)

    def zone_idx_for_device(self, device_id: str) -> str:
        """Return the underlying `zone_idx` key for a device (not the label)."""
        for zidx, roles in self.zone_devices.items():
            for _role, devs in roles.items():
                if device_id in devs:
                    return zidx
        return "unknown"

    def devices_in_zone(self, device_id: str) -> str:
        """Return the human label for a device's zone (used for `devices.zone`)."""
        for zidx, roles in self.zone_devices.items():
            for _role, devs in roles.items():
                if device_id in devs:
                    return self.zone_label(zidx)
        return "unknown"


def apply_payload(repo: Repository, item: Dict[str, Any], state: ZoneState) -> None:
    code = str(item.get("code") or "unknown").strip()
    code_name = item.get("code_name") or ""
    verb = item.get("verb") or "unknown"
    src = item.get("src_id") or "unknown"
    dst = item.get("dst_id") or "unknown"
    payload = item.get("payload")

    if isinstance(payload, dict):
        if (
            (code == "0004" or code == "zone_name" or code_name == "zone_name")
            and "zone_idx" in payload
            and "name" in payload
        ):
            zidx, zname = payload["zone_idx"], payload["name"]
            if zidx and zname:
                zkey = str(zidx)
                state.zone_names[zkey] = str(zname)
                repo.upsert_zone(zkey, str(zname))
                for role_devs in state.zone_devices.get(zkey, {}).values():
                    for did in role_devs:
                        if did and did != "unknown":
                            repo.update_device_zone(did, str(zname))

        if (
            (code == "000C" or code == "zone_devices")
            and "zone_idx" in payload
            and "device_role" in payload
        ):
            zidx = payload["zone_idx"]
            role = payload["device_role"]
            devices = payload.get("devices") or []
            if zidx and role is not None:
                if zidx not in state.zone_devices:
                    state.zone_devices[zidx] = {}
                state.zone_devices[zidx][str(role)] = list(devices) if devices else []
                lbl = state.zone_label(str(zidx))
                repo.upsert_zone(str(zidx), lbl if lbl != "unknown" else str(zidx))
                for did in devices:
                    if did and did != "unknown":
                        repo.update_device_zone(str(did), lbl)
                # If we already saw a controller zone temperature for this zone,
                # apply it now that we know which devices are in this zone.
                if str(zidx) in state.zone_temp_reports:
                    _distribute_zone_temp_report_to_zone(
                        repo, state, str(zidx), state.zone_temp_reports[str(zidx)]
                    )

        # zone_mode: following_schedule + target setpoint (per zone).
        if code_name == "zone_mode" and payload.get("zone_idx") is not None:
            try:
                zidx = str(payload.get("zone_idx")).strip()
                mode = payload.get("mode")
                following = (
                    str(mode).strip() == "follow_schedule" if mode is not None else None
                )
                sp = payload.get("setpoint")
                sp_f: Optional[float] = None
                if sp is not None and not isinstance(sp, str):
                    sp_f = float(sp)
                repo.update_zone_following_schedule(
                    zidx, following, setpoint_c=sp_f
                )
            except (TypeError, ValueError):
                pass

        if "temperature" in payload and payload["temperature"] is not None:
            # Some gateways/controllers broadcast per-zone values in `temperature`
            # payloads with `zone_idx` even when the sending device is the controller.
            # We treat those as controller-derived desired targets (separate from
            # device-reported temperatures / device-reported setpoint).
            try:
                t = float(payload["temperature"])
                zraw = payload.get("zone_idx") or payload.get("ufx_idx")
                if zraw is not None:
                    zidx = str(zraw).strip()
                    if zidx:
                        repo.update_zone_temperature(zidx, t)
                        state.zone_temp_reports[zidx] = t
                        _distribute_zone_temp_report_to_zone(repo, state, zidx, t)
                elif src != "unknown":
                    # If device reported temperature without zone_idx, map
                    # device->zone_idx (not label) for zone table updates.
                    zidx = state.zone_idx_for_device(src)
                    if zidx != "unknown":
                        repo.update_zone_temperature(zidx, t)
                    repo.update_device_temperature(src, t)
            except (TypeError, ValueError):
                logger.warning("Bad temperature in payload")

        if code_name == "dhw_params" and payload.get("setpoint") is not None:
            try:
                cid = src if src.startswith("01:") else dst
                if cid.startswith("01:"):
                    repo.update_device_setpoint(cid, float(payload["setpoint"]))
            except (TypeError, ValueError):
                pass

        if "setpoint" in payload and payload["setpoint"] is not None and code != "22D9":
            if code_name != "dhw_params":
                try:
                    sp = float(payload["setpoint"])
                    zraw = payload.get("zone_idx")
                    zidx = str(zraw).strip() if zraw is not None else ""
                    # Controller (01:) announces zone targets — apply to TRVs etc., not the controller.
                    if src.startswith("01:") and zidx:
                        repo.update_zone_setpoint(zidx, sp)
                        n = _distribute_setpoint_to_zone(repo, state, zidx, sp)
                        if n == 0 and _is_actuator_destination(dst):
                            repo.update_device_setpoint(dst, sp)
                    elif src != "unknown":
                        repo.update_device_setpoint(src, sp)
                except (TypeError, ValueError):
                    logger.warning("Bad setpoint in payload")

        if code == "22D9" and "setpoint" in payload:
            try:
                sp = float(payload["setpoint"])
                if src != "unknown":
                    repo.update_device_setpoint(src, sp)
            except (TypeError, ValueError):
                pass

        if code_name in ("dhw_temp",) and payload.get("temperature") is not None:
            try:
                cid = src if src.startswith("01:") else dst
                if cid.startswith("01:"):
                    repo.update_device_temperature(cid, float(payload["temperature"]))
            except (TypeError, ValueError):
                pass

        if (code == "12B0" or code_name == "window_state") and "window_open" in payload:
            wo = payload.get("window_open")
            if wo is not None:
                if isinstance(wo, str):
                    st = (
                        "open"
                        if wo.strip().lower() in ("1", "true", "yes", "on", "open")
                        else "closed"
                    )
                else:
                    st = "open" if wo else "closed"
                zraw = payload.get("zone_idx")
                zidx = str(zraw).strip() if zraw is not None else ""
                if src.startswith("01:") and zidx:
                    n = 0
                    for role_devs in state.zone_devices.get(zidx, {}).values():
                        for did in role_devs:
                            if did and did != "unknown":
                                repo.update_device_window_state(did, st)
                                n += 1
                    if n == 0 and _is_actuator_destination(dst):
                        repo.update_device_window_state(dst, st)
                elif src != "unknown":
                    repo.update_device_window_state(src, st)

    # Some systems send per-zone temperatures as a list of dicts:
    #   [{'zone_idx': '00', 'temperature': 18.11}, ...]
    if isinstance(payload, list) and src.startswith("01:"):
        if code_name == "temperature" or code == "30C9":
            for ent in payload:
                if not isinstance(ent, dict):
                    continue
                if ent.get("temperature") is None:
                    continue
                zraw = ent.get("zone_idx") or ent.get("ufx_idx")
                if zraw is None:
                    continue
                zidx = str(zraw).strip()
                if not zidx:
                    continue
                try:
                    t = float(ent["temperature"])
                except (TypeError, ValueError):
                    continue
                repo.update_zone_temperature(zidx, t)
                state.zone_temp_reports[zidx] = t
                _distribute_zone_temp_report_to_zone(repo, state, zidx, t)

    if isinstance(payload, list) and src.startswith("01:") and code_name == "setpoint":
        for ent in payload:
            if not isinstance(ent, dict):
                continue
            zraw = ent.get("zone_idx")
            if zraw is None or ent.get("setpoint") is None:
                continue
            try:
                sp = float(ent["setpoint"])
                zidx = str(zraw).strip()
                repo.update_zone_setpoint(zidx, sp)
                _distribute_setpoint_to_zone(repo, state, zidx, sp)
            except (TypeError, ValueError):
                logger.warning("Bad setpoint in setpoint list payload")

    if code == "3150" or code_name == "heat_demand":
        _apply_heat_demand(repo, state, src, payload)

    if (code == "1060" or code_name == "device_battery") and isinstance(
        payload, dict
    ):
        if src and src != "unknown":
            bl_raw = payload.get("battery_level")
            level_pct: Optional[float] = None
            if bl_raw is not None and not isinstance(bl_raw, str):
                try:
                    level_pct = round(float(bl_raw) * 100.0, 1)
                except (TypeError, ValueError):
                    pass
            repo.update_device_battery(src, level_pct, bool(payload.get("battery_low")))

    if isinstance(payload, dict):
        for did in (src, dst):
            if did and did != "unknown":
                z = state.devices_in_zone(did)
                if z != "unknown":
                    repo.update_device_zone(did, z)

    try_record_fault_log(repo, item)
