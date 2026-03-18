"""ramses_tx version, USB serial identity, optional evofw3 !V firmware line."""

from __future__ import annotations

import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _read_ramses_tx_version_from_file(ramses_src: Path) -> Optional[str]:
    ver_py = ramses_src / "ramses_tx" / "version.py"
    if not ver_py.is_file():
        return None
    try:
        text = ver_py.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    m = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', text)
    return m.group(1).strip() if m else None


def get_ramses_tx_version(ramses_rf_src: Path) -> str:
    """Version string of bundled ramses_tx (same tree as RAMSES_RF_PATH)."""
    v = _read_ramses_tx_version_from_file(ramses_rf_src)
    if v:
        return v
    sp = str(ramses_rf_src.resolve())
    if sp not in sys.path:
        sys.path.insert(0, sp)
    try:
        from ramses_tx.version import VERSION  # type: ignore

        return str(VERSION)
    except Exception as e:
        logger.debug("Could not import ramses_tx.version: %s", e)
        return "unknown"


def get_usb_serial_identity(port: str) -> Dict[str, Any]:
    """USB descriptor fields for the configured serial device (if found)."""
    out: Dict[str, Any] = {
        "usb_serial_port": port,
        "usb_product": "",
        "usb_manufacturer": "",
        "usb_vid": "",
        "usb_pid": "",
        "usb_serial_number": "",
        "usb_hwid": "",
    }
    try:
        from serial.tools import list_ports
    except ImportError:
        return out
    try:
        want = os.path.realpath(port) if os.path.exists(port) else port
    except OSError:
        want = port
    for p in list_ports.comports(include_links=True):
        dev = p.device
        try:
            real = os.path.realpath(dev) if os.path.exists(dev) else dev
        except OSError:
            real = dev
        if real == want or p.device == port or dev == port:
            out["usb_product"] = (p.product or "").strip()
            out["usb_manufacturer"] = (p.manufacturer or "").strip()
            out["usb_vid"] = f"{p.vid:04X}" if p.vid is not None else ""
            out["usb_pid"] = f"{p.pid:04X}" if p.pid is not None else ""
            sn = getattr(p, "serial_number", None) or ""
            out["usb_serial_number"] = str(sn).strip() if sn else ""
            out["usb_hwid"] = (p.hwid or "").strip()
            break
    return out


def probe_evofw3_version_line(port: str, timeout: float = 0.45) -> Optional[str]:
    """
    Send evofw3 '!V' once (port must be free). Typical: '# evofw3 0.7.x'.
    """
    try:
        import serial
    except ImportError:
        return None
    try:
        ser = serial.Serial(
            port=port,
            baudrate=115200,
            timeout=timeout,
            write_timeout=timeout,
        )
        try:
            ser.reset_input_buffer()
            ser.write(b"!V\r\n")
            raw = ser.readline()
        finally:
            ser.close()
        if not raw:
            return None
        return raw.decode("ascii", errors="replace").strip()
    except Exception as e:
        logger.debug("evofw3 !V probe failed for %s: %s", port, e)
        return None


def gather_runtime_versions(
    *,
    ramses_port: Optional[str],
    gateway_type: str,
    ramses_rf_src: Path,
    no_device: bool,
) -> Dict[str, Any]:
    if ramses_rf_src.is_dir():
        ver = get_ramses_tx_version(ramses_rf_src)
        path_str = str(ramses_rf_src.resolve())
    else:
        ver = "unknown"
        path_str = str(ramses_rf_src)
    meta: Dict[str, Any] = {
        "ramses_tx_version": ver,
        "ramses_rf_path": path_str,
    }
    if no_device or not ramses_port:
        meta["stick_firmware_line"] = None
        meta["usb_serial_port"] = None
        meta["usb_product"] = ""
        meta["usb_manufacturer"] = ""
        meta["usb_vid"] = ""
        meta["usb_pid"] = ""
        meta["usb_serial_number"] = ""
        meta["usb_hwid"] = ""
        return meta

    meta.update(get_usb_serial_identity(ramses_port))
    # HGI80: do not send !V. evofw3: probe. auto: probe only if not Honeywell VID.
    if gateway_type == "hgi80":
        meta["stick_firmware_line"] = None
    elif gateway_type == "evofw3":
        meta["stick_firmware_line"] = probe_evofw3_version_line(ramses_port)
    elif meta.get("usb_vid") == "10AC":
        meta["stick_firmware_line"] = None
    elif not meta.get("usb_vid"):
        meta["stick_firmware_line"] = None
    else:
        meta["stick_firmware_line"] = probe_evofw3_version_line(ramses_port)
    return meta
