"""PyMySQL connection factory."""

from __future__ import annotations

from typing import Any, Dict

import pymysql


def connect(creds: Dict[str, Any], *, database: str | None = None):
    """Return a new connection. If database is None, use creds['database']."""
    kw = dict(creds)
    if database is not None:
        kw["database"] = database
    return pymysql.connect(
        host=kw["host"],
        port=int(kw["port"]),
        user=kw["user"],
        password=kw["password"],
        database=kw["database"],
        charset=kw.get("charset", "utf8mb4"),
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def connect_server_only(creds: Dict[str, Any]):
    """Connect without default database (for CREATE DATABASE)."""
    return pymysql.connect(
        host=creds["host"],
        port=int(creds["port"]),
        user=creds["user"],
        password=creds["password"],
        charset=creds.get("charset", "utf8mb4"),
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )
