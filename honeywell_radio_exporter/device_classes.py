"""
RAMSES-II device type prefix (hex before ':') → human description.
Aligned with ramses_tx.const.DevType / DEV_TYPE_MAP.
"""

from __future__ import annotations

from typing import Optional

# 2-char lowercase hex → short label for UI
DEVICE_CLASS_DESCRIPTIONS: dict[str, str] = {
    "00": "TRV (radiator valve)",
    "01": "Controller",
    "02": "UFH controller",
    "03": "Analog thermostat",
    "04": "TRV (radiator valve)",
    "07": "DHW sensor",
    "08": "Jasper interface module",
    "10": "OpenTherm bridge",
    "12": "Digital thermostat (DTS92)",
    "13": "BDR / electrical relay",
    "17": "Outdoor sensor",
    "18": "HGI80 gateway",
    "22": "Digital thermostat (DTS92)",
    "23": "Programmer",
    "30": "RF gateway (RFG100)",
    "31": "Jasper thermostat",
    "34": "Round thermostat (TR87RF)",
    "63": "Broadcast / generic",
}


def normalize_class_prefix(device_id: str) -> str:
    if not device_id or device_id == "unknown":
        return ""
    part = device_id.split(":", 1)[0].strip().lower()
    if not part:
        return ""
    if len(part) == 1:
        part = "0" + part
    return part[:2] if len(part) >= 2 else part.zfill(2)


def describe_device_class(device_id: str) -> tuple[str, Optional[str]]:
    """
    Returns (hex_prefix, description_or_none).
    Unknown classes still get a short explanation.
    """
    p = normalize_class_prefix(device_id)
    if not p:
        return "", None
    desc = DEVICE_CLASS_DESCRIPTIONS.get(p)
    if desc:
        return p, desc
    return p, f"Unknown device type ({p})"
