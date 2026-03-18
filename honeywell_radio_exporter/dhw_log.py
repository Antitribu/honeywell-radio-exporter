"""Track DHW (hot water) status from RAMSES payloads into dhw_status table."""

from __future__ import annotations

from typing import Any, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from honeywell_radio_exporter.db.repository import Repository


def _controller_id(src: str, dst: str) -> str:
    if src.startswith("01:"):
        return src
    if dst.startswith("01:"):
        return dst
    return src or dst


def try_record_dhw_status(repo: "Repository", item: Dict[str, Any]) -> None:
    code = str(item.get("code") or "").strip().upper()
    cn = (item.get("code_name") or "").strip().lower()
    src = str(item.get("src_id") or "").strip()
    dst = str(item.get("dst_id") or "").strip()
    payload = item.get("payload")
    if not isinstance(payload, dict):
        return

    if cn not in ("dhw_temp", "dhw_params", "dhw_mode") and code not in (
        "1260",
        "10A0",
        "1F41",
    ):
        return

    idx = str(payload.get("dhw_idx") or "00").strip()[:8] or "00"
    patch: Dict[str, Any] = {"controller_id": _controller_id(src, dst)}

    if cn == "dhw_temp" or code == "1260":
        t = payload.get("temperature")
        if t is not None and not isinstance(t, str):
            patch["temperature_c"] = float(t)

    if cn == "dhw_params" or code == "10A0":
        sp = payload.get("setpoint")
        if sp is not None and not isinstance(sp, str):
            patch["setpoint_c"] = float(sp)
        if payload.get("overrun") is not None:
            patch["overrun"] = payload.get("overrun")
        if payload.get("differential") is not None:
            patch["differential_c"] = payload.get("differential")

    if cn == "dhw_mode" or code == "1F41":
        if "mode" in payload and payload.get("mode") is not None:
            patch["mode"] = str(payload.get("mode"))
        if "active" in payload:
            patch["active"] = payload.get("active")

    repo.merge_dhw_status(idx, patch)

