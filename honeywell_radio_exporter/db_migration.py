"""
Apply versioned schema migrations on startup.
Compares schema_migrations table and runs pending SQL steps.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Tuple

logger = logging.getLogger(__name__)

# Each migration: (version, [sql statements])
MIGRATIONS: List[Tuple[int, List[str]]] = [
    (
        1,
        [
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INT NOT NULL PRIMARY KEY,
                applied_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS devices (
                device_id VARCHAR(32) NOT NULL PRIMARY KEY,
                name VARCHAR(255) NULL,
                zone VARCHAR(255) NULL,
                type VARCHAR(64) NULL,
                last_seen DATETIME(6) NULL,
                messages_from INT NOT NULL DEFAULT 0,
                messages_to INT NOT NULL DEFAULT 0,
                acks_from INT NOT NULL DEFAULT 0,
                acks_to INT NOT NULL DEFAULT 0,
                setpoint DECIMAL(6,2) NULL,
                temperature DECIMAL(6,2) NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS messages (
                id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                received_at DATETIME(6) NOT NULL,
                code VARCHAR(32) NOT NULL,
                verb VARCHAR(8) NOT NULL,
                src_id VARCHAR(32) NOT NULL,
                dst_id VARCHAR(32) NOT NULL,
                payload_json JSON NULL,
                raw TEXT NULL,
                validation_ok TINYINT(1) NOT NULL DEFAULT 1,
                INDEX ix_messages_received_at (received_at),
                INDEX ix_messages_src (src_id),
                INDEX ix_messages_dst (dst_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
        ],
    ),
    (
        2,
        [
            """
            CREATE TABLE IF NOT EXISTS zones (
                zone_idx VARCHAR(32) NOT NULL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
                    ON UPDATE CURRENT_TIMESTAMP(6)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS message_code_counts (
                code VARCHAR(32) NOT NULL PRIMARY KEY,
                code_name VARCHAR(128) NULL,
                message_count BIGINT UNSIGNED NOT NULL DEFAULT 0,
                last_message_at DATETIME(6) NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            INSERT INTO message_code_counts (code, code_name, message_count, last_message_at)
            SELECT code, NULL, COUNT(*), MAX(received_at) FROM messages GROUP BY code
            """,
        ],
    ),
    (
        3,
        ["""
            CREATE TABLE IF NOT EXISTS fault_log_entries (
                id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                received_at DATETIME(6) NOT NULL,
                log_idx VARCHAR(8) NULL,
                event_timestamp VARCHAR(64) NULL,
                fault_state VARCHAR(32) NULL,
                fault_type VARCHAR(64) NULL,
                detail_json JSON NULL,
                device_id VARCHAR(32) NULL,
                src_id VARCHAR(32) NOT NULL DEFAULT '',
                dst_id VARCHAR(32) NOT NULL DEFAULT '',
                verb VARCHAR(8) NOT NULL DEFAULT '',
                INDEX ix_fault_received (received_at),
                INDEX ix_fault_event (event_timestamp)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """],
    ),
    (
        4,
        [
            """
            ALTER TABLE messages ADD INDEX ix_messages_code (code)
            """
        ],
    ),
    (
        5,
        ["""
            CREATE TABLE IF NOT EXISTS puzzle_version_events (
                id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                received_at DATETIME(6) NOT NULL,
                src_id VARCHAR(32) NOT NULL,
                dst_id VARCHAR(32) NOT NULL DEFAULT '',
                engine_version VARCHAR(64) NOT NULL DEFAULT '',
                parser_version VARCHAR(64) NOT NULL DEFAULT '',
                prev_engine VARCHAR(64) NULL,
                prev_parser VARCHAR(64) NULL,
                is_initial TINYINT(1) NOT NULL DEFAULT 0,
                INDEX ix_puzzle_src (src_id),
                INDEX ix_puzzle_received (received_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """],
    ),
    (
        6,
        [
            """
            ALTER TABLE devices ADD COLUMN heat_demand DECIMAL(5,2) NULL
            """
        ],
    ),
    (
        7,
        [
            """
            ALTER TABLE devices ADD COLUMN battery_pct DECIMAL(5,2) NULL,
            ADD COLUMN battery_low TINYINT(1) NOT NULL DEFAULT 0
            """
        ],
    ),
    (
        8,
        ["""
            CREATE TABLE IF NOT EXISTS boiler_status (
                otb_device_id VARCHAR(32) NOT NULL PRIMARY KEY,
                updated_at DATETIME(6) NOT NULL,
                flame_on TINYINT(1) NULL,
                ch_active TINYINT(1) NULL,
                dhw_active TINYINT(1) NULL,
                ch_enabled TINYINT(1) NULL,
                modulation_pct DECIMAL(5,2) NULL,
                ch_setpoint_c SMALLINT NULL,
                flow_temp_c DECIMAL(6,2) NULL,
                return_temp_c DECIMAL(6,2) NULL,
                target_setpoint_c DECIMAL(6,2) NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """],
    ),
    (
        9,
        [
            "ALTER TABLE devices ADD COLUMN window_state VARCHAR(16) NULL",
        ],
    ),
    (
        10,
        [
            "ALTER TABLE messages ADD COLUMN zone VARCHAR(32) NULL",
            "ALTER TABLE messages ADD INDEX ix_messages_zone (zone)",
            "ALTER TABLE messages ADD INDEX ix_messages_src_received (src_id, received_at)",
            "ALTER TABLE messages ADD INDEX ix_messages_dst_received (dst_id, received_at)",
        ],
    ),
    (
        11,
        [
            "ALTER TABLE devices ADD COLUMN last_seen_from DATETIME(6) NULL",
            "ALTER TABLE devices ADD COLUMN last_seen_to DATETIME(6) NULL",
            "ALTER TABLE devices ADD INDEX ix_devices_last_seen_from (last_seen_from)",
            "ALTER TABLE devices ADD INDEX ix_devices_last_seen_to (last_seen_to)",
        ],
    ),
    (
        12,
        [
            """
            CREATE TABLE IF NOT EXISTS dhw_status (
                dhw_idx VARCHAR(8) NOT NULL PRIMARY KEY,
                updated_at DATETIME(6) NOT NULL,
                controller_id VARCHAR(32) NULL,
                mode VARCHAR(64) NULL,
                active TINYINT(1) NULL,
                temperature_c DECIMAL(6,2) NULL,
                setpoint_c DECIMAL(6,2) NULL,
                overrun SMALLINT NULL,
                differential_c DECIMAL(6,2) NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            "ALTER TABLE dhw_status ADD INDEX ix_dhw_updated (updated_at)",
        ],
    ),
    (
        13,
        [
            "ALTER TABLE devices ADD COLUMN last_ack DATETIME(6) NULL",
            "ALTER TABLE devices ADD INDEX ix_devices_last_ack (last_ack)",
        ],
    ),
    (
        14,
        [
            "ALTER TABLE devices ADD COLUMN desired_setpoint DECIMAL(6,2) NULL",
            "ALTER TABLE devices ADD INDEX ix_devices_desired_setpoint (desired_setpoint)",
        ],
    ),
    (
        15,
        [
            "ALTER TABLE devices ADD COLUMN zone_temp_report DECIMAL(6,2) NULL",
            "ALTER TABLE devices ADD INDEX ix_devices_zone_temp_report (zone_temp_report)",
        ],
    ),
    (
        16,
        [
            "ALTER TABLE zones ADD COLUMN following_schedule TINYINT(1) NULL",
            "ALTER TABLE zones ADD COLUMN setpoint_c DECIMAL(6,2) NULL",
            "ALTER TABLE zones ADD COLUMN temperature_c DECIMAL(6,2) NULL",
            "ALTER TABLE zones ADD COLUMN heat_demand_pct DECIMAL(5,2) NULL",
            "ALTER TABLE zones ADD COLUMN message_count BIGINT UNSIGNED NOT NULL DEFAULT 0",
            "ALTER TABLE zones ADD INDEX ix_zones_message_count (message_count)",
        ],
    ),
    (
        17,
        [
            "ALTER TABLE zones ADD COLUMN rq_message_count BIGINT UNSIGNED NOT NULL DEFAULT 0",
            "ALTER TABLE zones ADD COLUMN rp_message_count BIGINT UNSIGNED NOT NULL DEFAULT 0",
            "ALTER TABLE zones ADD COLUMN other_message_count BIGINT UNSIGNED NOT NULL DEFAULT 0",
        ],
    ),
]


def _applied_versions(cur) -> set:
    try:
        cur.execute("SELECT version FROM schema_migrations")
        return {row["version"] for row in cur.fetchall()}
    except Exception:
        return set()


def run_migrations(conn_factory: Callable[[], Any]) -> None:
    """
    conn_factory returns a DB connection (with database selected).
    Runs each migration whose version is not in schema_migrations.
    """
    conn = conn_factory()
    try:
        cur = conn.cursor()
        applied = _applied_versions(cur)
        for version, statements in MIGRATIONS:
            if version in applied:
                continue
            logger.info("Applying database migration version %s", version)
            for sql in statements:
                stmt = " ".join(sql.split())
                cur.execute(stmt)
            cur.execute(
                "INSERT INTO schema_migrations (version) VALUES (%s)",
                (version,),
            )
            conn.commit()
            logger.info("Migration %s applied successfully", version)
            applied.add(version)
    finally:
        conn.close()


def ensure_database_exists(creds: Dict[str, Any]) -> None:
    """CREATE DATABASE IF NOT EXISTS using server-only connection."""
    from honeywell_radio_exporter.db.connection import connect_server_only

    db_name = creds["database"]
    conn = connect_server_only(creds)
    try:
        cur = conn.cursor()
        cur.execute(
            f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
    finally:
        conn.close()
