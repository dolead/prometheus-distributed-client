import sqlite3
from typing import Union

from redis import Redis

_CONFIG = {}


def setup(
    redis: Redis, redis_prefix: str = "prometheus", redis_expire: int = 3600
):
    _CONFIG["redis"] = redis
    _CONFIG["redis_prefix"] = redis_prefix
    _CONFIG["redis_expire"] = redis_expire


def setup_sqlite(
    sqlite: Union[sqlite3.Connection, str],
    sqlite_prefix: str = "prometheus",
):
    """Setup SQLite backend.

    Args:
        sqlite: SQLite connection or path to database file
        sqlite_prefix: Prefix for metric keys

    Note:
        Unlike Redis, SQLite does not use TTL/expiration. SQLite is
        file-based and typically not shared between applications, so
        metrics are cleaned up when the file is deleted (e.g., on
        container restart).
    """
    if isinstance(sqlite, str):
        conn = sqlite3.Connection(sqlite)
    else:
        conn = sqlite

    # Create table if it doesn't exist
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS metrics (
            metric_key TEXT NOT NULL,
            subkey TEXT NOT NULL,
            value REAL NOT NULL,
            PRIMARY KEY (metric_key, subkey)
        )
        """
    )
    conn.commit()

    _CONFIG["sqlite"] = conn
    _CONFIG["sqlite_prefix"] = sqlite_prefix


def get_redis_conn() -> Redis:
    return _CONFIG["redis"]


def get_redis_expire() -> int:
    return _CONFIG["redis_expire"]


def get_redis_key(name) -> str:
    return f"{_CONFIG['redis_prefix']}_{name}"


def get_sqlite_conn() -> sqlite3.Connection:
    return _CONFIG["sqlite"]


def get_sqlite_key(name) -> str:
    return f"{_CONFIG['sqlite_prefix']}_{name}"
