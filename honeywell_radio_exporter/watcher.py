"""RAMSES gateway thread: push messages onto queue and raw rotating logs."""

from __future__ import annotations

import asyncio
import logging
import logging.handlers
import os
import queue
import sys
import threading
from pathlib import Path
from typing import Any, Callable, Dict


logger = logging.getLogger(__name__)


def _apply_gateway_type_override(ramses_port: str, gateway_type: str) -> None:
    """
    ramses_rf guesses HGI80 vs evofw3 from USB VID / by-id path. Plain /dev/ttyACM0
    often yields "unknown" → warning + assume evofw3. Force the correct stack here.
    """
    if gateway_type not in ("hgi80", "evofw3"):
        return
    import ramses_tx.transport as tx

    try:
        port_real = os.path.realpath(ramses_port)
    except OSError:
        port_real = ramses_port
    _orig = tx.is_hgi80

    def _patched(ser_port: str):
        try:
            sr = os.path.realpath(ser_port) if os.path.exists(ser_port) else ser_port
        except OSError:
            sr = ser_port
        if ser_port == ramses_port or sr == port_real:
            return gateway_type == "hgi80"
        return _orig(ser_port)

    tx.is_hgi80 = _patched  # type: ignore[method-assign]
    logger.info(
        "Gateway type forced to %s for %s (USB auto-detect skipped)",
        gateway_type,
        ramses_port,
    )


def setup_raw_message_logging(log_dir: Path, max_bytes: int, backup_count: int) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / "raw_messages.log"
    h = logging.handlers.RotatingFileHandler(
        path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    h.setLevel(logging.INFO)
    h.setFormatter(logging.Formatter("%(message)s"))
    lg = logging.getLogger("honeywell.raw_messages")
    lg.handlers.clear()
    lg.addHandler(h)
    lg.setLevel(logging.INFO)
    lg.propagate = False


def _msg_to_item(msg: Any, get_code_name: Callable[[Any], str]) -> Dict[str, Any]:
    code = str(msg.code) if getattr(msg, "code", None) else "unknown"
    verb = str(msg.verb) if getattr(msg, "verb", None) else "unknown"
    src = str(msg.src.id) if msg.src and hasattr(msg.src, "id") else "unknown"
    dst = str(msg.dst.id) if msg.dst and hasattr(msg.dst, "id") else "unknown"
    payload = msg.payload if isinstance(getattr(msg, "payload", None), dict) else None
    return {
        "code": code,
        "verb": verb,
        "src_id": src,
        "dst_id": dst,
        "payload": payload,
        "raw": str(msg),
        "code_name": get_code_name(msg.code) if msg.code else None,
    }


def run_watcher_thread(
    msg_queue: "queue.Queue[Dict[str, Any]]",
    ramses_port: str,
    stop_event: threading.Event,
    raw_log_dir: Path,
    raw_max_bytes: int,
    raw_backup_count: int,
    gateway_type: str = "auto",
) -> None:
    from honeywell_radio_exporter import config as _cfg

    ramses_rf_path = _cfg.RAMSES_RF_SRC
    if ramses_rf_path.is_dir() and str(ramses_rf_path) not in sys.path:
        sys.path.insert(0, str(ramses_rf_path))

    from ramses_rf import Gateway, Message  # pylint: disable=import-error
    from ramses_tx.message import CODE_NAMES  # pylint: disable=import-error
    from ramses_tx.ramses import CODES_SCHEMA  # pylint: disable=import-error

    _apply_gateway_type_override(ramses_port, gateway_type)

    def get_code_name(code: Any) -> str:
        if not code:
            return "unknown"
        try:
            if code in CODE_NAMES:
                return CODE_NAMES[code]
            code_str = str(code)
            for code_key, schema in CODES_SCHEMA.items():
                if str(code_key) == code_str:
                    n = schema.get("name")
                    if n:
                        return n
        except (AttributeError, KeyError, TypeError):
            pass
        return str(code)

    setup_raw_message_logging(raw_log_dir, raw_max_bytes, raw_backup_count)
    raw_lg = logging.getLogger("honeywell.raw_messages")

    async def async_main() -> None:
        gw = Gateway(
            port_name=ramses_port,
            loop=asyncio.get_event_loop(),
            config={"enable_eavesdrop": True},
        )

        def on_msg(msg: Message) -> None:
            raw_lg.info(str(msg))
            try:
                item = _msg_to_item(msg, get_code_name)
                msg_queue.put_nowait(item)
            except queue.Full:
                logger.error("Message queue full, dropping message")

        gw.add_msg_handler(on_msg)
        await gw.start()
        logger.info("RAMSES gateway started on %s", ramses_port)
        while not stop_event.is_set():
            await asyncio.sleep(0.25)
        await gw.stop()

    try:
        asyncio.run(async_main())
    except Exception as e:
        logger.exception("Watcher failed: %s", e)
