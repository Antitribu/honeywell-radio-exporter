"""Database migration tests (require MySQL)."""

import os

import pytest

pytestmark = pytest.mark.integration


def _mysql_test_creds():
    host = os.environ.get("MYSQL_TEST_HOST")
    if not host:
        return None
    return {
        "host": host,
        "port": int(os.environ.get("MYSQL_TEST_PORT", "3306")),
        "user": os.environ.get("MYSQL_TEST_USER", "root"),
        "password": os.environ.get("MYSQL_TEST_PASSWORD", ""),
        "database": os.environ.get("MYSQL_TEST_DATABASE", "honeywell_exporter_test"),
        "charset": "utf8mb4",
    }


@pytest.fixture
def test_creds():
    c = _mysql_test_creds()
    if not c:
        pytest.skip("Set MYSQL_TEST_HOST to run integration DB tests")
    return c


def test_migrations_idempotent(test_creds):
    import pymysql

    from honeywell_radio_exporter.db_migration import (
        ensure_database_exists,
        run_migrations,
    )

    ensure_database_exists(test_creds)
    conn = pymysql.connect(
        host=test_creds["host"],
        port=test_creds["port"],
        user=test_creds["user"],
        password=test_creds["password"],
        database=test_creds["database"],
        charset="utf8mb4",
    )
    conn.close()

    def factory():
        return pymysql.connect(
            host=test_creds["host"],
            port=int(test_creds["port"]),
            user=test_creds["user"],
            password=test_creds["password"],
            database=test_creds["database"],
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False,
        )

    run_migrations(factory)
    run_migrations(factory)

    c2 = factory()
    try:
        cur = c2.cursor()
        cur.execute(
            "SELECT COUNT(*) AS n FROM information_schema.tables "
            "WHERE table_schema=%s AND table_name='devices'",
            (test_creds["database"],),
        )
        row = cur.fetchone()
        assert row["n"] == 1
        cur.execute("SELECT COUNT(*) AS n FROM schema_migrations")
        assert cur.fetchone()["n"] >= 6
        for tbl in (
            "zones",
            "message_code_counts",
            "fault_log_entries",
            "puzzle_version_events",
            "boiler_status",
            "dhw_status",
        ):
            cur.execute(
                "SELECT COUNT(*) AS n FROM information_schema.tables "
                "WHERE table_schema=%s AND table_name=%s",
                (test_creds["database"], tbl),
            )
            assert cur.fetchone()["n"] == 1
    finally:
        c2.close()
