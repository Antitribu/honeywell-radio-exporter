"""Load MySQL credentials from KEY=value file (.mysql_creds)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)


def load_mysql_creds(path: Path) -> Dict[str, Any]:
    """
    Parse lines like host=..., port=3306, user=..., password=..., database=...
    Keys are case-insensitive; aliases: db -> database.
    """
    if not path.is_file():
        raise FileNotFoundError(f"MySQL creds file not found: {path}")
    out: Dict[str, Any] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip().lower()
            v = v.strip()
            if k == "db":
                k = "database"
            out[k] = v
    required = ("host", "user", "password", "database")
    missing = [r for r in required if r not in out]
    if missing:
        raise ValueError(f".mysql_creds missing keys: {missing}")
    port = int(out.get("port", 3306))
    out["port"] = port
    return {
        "host": out["host"],
        "port": port,
        "user": out["user"],
        "password": out["password"],
        "database": out["database"],
        "charset": "utf8mb4",
    }
