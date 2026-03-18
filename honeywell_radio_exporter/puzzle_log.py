"""Record gateway puzzle_packet (7FFF) engine/parser version changes."""

from __future__ import annotations

from typing import Any, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from honeywell_radio_exporter.db.repository import Repository


def try_record_puzzle_version(repo: "Repository", item: Dict[str, Any]) -> None:
    """
    When ramses_rf parses a signature puzzle (engine + parser versions),
    store a row only on first sighting or when engine/parser changes for that gateway.
    """
    code = str(item.get("code") or "").strip().upper()
    cn = (item.get("code_name") or "").strip().lower()
    if code != "7FFF" and cn != "puzzle_packet":
        return
    p = item.get("payload")
    if not isinstance(p, dict):
        return
    eng = str(p.get("engine") or "").strip()[:64]
    par = str(p.get("parser") or "").strip()[:64]
    if not eng and not par:
        return
    src = str(item.get("src_id") or "").strip()[:32]
    if not src or src == "unknown":
        return
    dst = str(item.get("dst_id") or "").strip()[:32]
    repo.record_puzzle_version_event(
        src_id=src,
        dst_id=dst if dst != "unknown" else "",
        engine_version=eng,
        parser_version=par,
    )
