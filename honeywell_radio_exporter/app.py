"""Honeywell RAMSES monitor: migrations, watcher, consumer, janitor, HTTP."""

from __future__ import annotations

import argparse
import logging
import logging.handlers
import os
import queue
import sys
import threading
from pathlib import Path

from honeywell_radio_exporter import config
from honeywell_radio_exporter.consumer import run_consumer
from honeywell_radio_exporter.db.connection import connect
from honeywell_radio_exporter.db.creds import load_mysql_creds
from honeywell_radio_exporter.db.repository import Repository
from honeywell_radio_exporter.db_migration import ensure_database_exists, run_migrations
from honeywell_radio_exporter.warning_buffer import (
    attach_warning_buffer_handler,
    get_recent_warnings,
)
from honeywell_radio_exporter.janitor import run_janitor
from honeywell_radio_exporter.live_events import LiveNotifier
from honeywell_radio_exporter.log_rotation import (
    rotate_log_on_startup,
    should_rotate_on_startup,
)
from honeywell_radio_exporter.metrics_http import start_http_server
from honeywell_radio_exporter.runtime_versions import gather_runtime_versions
from honeywell_radio_exporter.watcher import run_watcher_thread


def _setup_logging() -> None:
    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    root.addHandler(ch)
    if should_rotate_on_startup():
        rotate_log_on_startup(config.MESSAGES_LOG, backup_count=5)
    fh = logging.handlers.RotatingFileHandler(
        config.MESSAGES_LOG,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    fh.setLevel(logging.INFO)
    fh.setFormatter(fmt)
    root.addHandler(fh)
    attach_warning_buffer_handler()


def main() -> None:
    parser = argparse.ArgumentParser(description="Honeywell RAMSES radio monitor")
    parser.add_argument("--port", type=int, default=config.HTTP_PORT)
    parser.add_argument(
        "--host",
        default=config.HTTP_BIND,
        metavar="ADDR",
        help="HTTP bind address (default: 0.0.0.0 = all interfaces; use 127.0.0.1 for local only)",
    )
    parser.add_argument("--ramses-port", type=str, default=config.DEFAULT_RAMSES_PORT)
    parser.add_argument(
        "--gateway-type",
        choices=("auto", "hgi80", "evofw3"),
        default="auto",
        help="USB RF stick: auto-detect (may warn on /dev/ttyACM0), hgi80=Honeywell HGI80, "
        "evofw3=ESP32/evofw3. Env RAMSES_GATEWAY_TYPE=hgi80|evofw3 used when --gateway-type auto.",
    )
    parser.add_argument(
        "--no-device",
        action="store_true",
        help="Do not open USB (HTTP + DB consumer only)",
    )
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    gateway_type = args.gateway_type
    if gateway_type == "auto":
        ev = os.environ.get("RAMSES_GATEWAY_TYPE", "").strip().lower()
        if ev in ("hgi80", "evofw3"):
            gateway_type = ev
    _setup_logging()
    logging.getLogger().setLevel(getattr(logging, args.log_level.upper(), logging.INFO))
    log = logging.getLogger(__name__)

    creds_path = Path(os.environ.get("MYSQL_CREDS_PATH", config.MYSQL_CREDS_PATH))
    try:
        creds = load_mysql_creds(creds_path)
    except Exception as e:
        log.error("MySQL creds: %s", e)
        sys.exit(1)

    try:
        ensure_database_exists(creds)
        run_migrations(lambda: connect(creds))
        # After adding new zone-count columns, ensure the verb split matches
        # total counts already accumulated in older DBs.
        conn = connect(creds)
        try:
            Repository(conn).resync_zone_message_counts_if_out_of_sync()
        finally:
            conn.close()
    except Exception as e:
        log.error("Database migration failed: %s", e)
        sys.exit(1)

    msg_queue: queue.Queue = queue.Queue(maxsize=config.MESSAGE_QUEUE_MAXSIZE)
    stop = threading.Event()
    live = LiveNotifier()

    def load_dashboard():
        conn = connect(creds)
        try:
            repo = Repository(conn)
            return {
                "devices": repo.list_devices_for_api(),
                "zones": repo.list_zones_for_api(),
                "message_code_counts": repo.list_message_code_counts_for_api(),
                "fault_log": repo.list_fault_log_for_api(),
                "puzzle_log": repo.list_puzzle_log_for_api(),
                "boiler_status": repo.list_boiler_status_for_api(),
                "dhw_status": repo.list_dhw_status_for_api(),
                "recent_warnings": get_recent_warnings(),
            }
        finally:
            conn.close()

    t_cons = threading.Thread(
        target=run_consumer,
        args=(creds, msg_queue, stop, live),
        name="consumer",
        daemon=True,
    )
    t_cons.start()

    t_jan = threading.Thread(
        target=run_janitor,
        args=(
            creds,
            stop,
            config.JANITOR_INTERVAL_SEC,
            config.MESSAGE_RETENTION_HOURS,
            config.DEVICE_STALE_DAYS,
            live,
        ),
        name="janitor",
        daemon=True,
    )
    t_jan.start()

    runtime_versions = gather_runtime_versions(
        ramses_port=args.ramses_port.strip() or None,
        gateway_type=gateway_type,
        ramses_rf_src=config.RAMSES_RF_SRC,
        no_device=args.no_device,
    )
    if runtime_versions.get("stick_firmware_line"):
        log.info("USB stick firmware (!V): %s", runtime_versions["stick_firmware_line"])

    if not args.no_device and args.ramses_port:
        t_watch = threading.Thread(
            target=run_watcher_thread,
            args=(
                msg_queue,
                args.ramses_port,
                stop,
                config.RAW_MESSAGES_LOG_DIR,
                config.RAW_LOG_MAX_BYTES,
                config.RAW_LOG_BACKUP_COUNT,
                gateway_type,
            ),
            name="watcher",
            daemon=True,
        )
        t_watch.start()
    else:
        log.warning("Running without RAMSES USB watcher")

    try:
        httpd = start_http_server(
            creds,
            args.port,
            load_dashboard,
            host=args.host,
            live_events=live,
            runtime_versions=runtime_versions,
        )
        log.info(
            "HTTP listening on %s:%s (/ui/ /api/devices /api/events /metrics/)",
            args.host or "0.0.0.0",
            args.port,
        )
        httpd.serve_forever()
    except KeyboardInterrupt:
        log.info("Shutdown")
    finally:
        stop.set()


if __name__ == "__main__":
    main()
