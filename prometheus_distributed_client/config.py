import sqlite3
from typing import Union, Optional

from redis import Redis

_CONFIG = {}


def setup(
    redis: Optional[Redis] = None,
    sqlite: Optional[Union[sqlite3.Connection, str]] = None,
    redis_prefix: str = "prometheus",
    redis_expire: int = 3600,
):
    """Setup metrics backend (Redis or SQLite).

    Args:
        redis: Redis connection (mutually exclusive with sqlite)
        sqlite: SQLite connection or path to database file
            (mutually exclusive with redis)
        redis_prefix: Prefix for metric keys (Redis only)
        redis_expire: TTL in seconds for metrics (Redis only)

    Examples:
        # Redis backend
        from redis import Redis
        setup(
            redis=Redis(host='localhost', port=6379),
            redis_prefix='myapp',
            redis_expire=3600
        )

        # SQLite backend (connection object)
        import sqlite3
        setup(sqlite=sqlite3.connect('metrics.db'))

        # SQLite backend (file path)
        setup(sqlite='metrics.db')

    Note:
        - Must provide either redis or sqlite, not both
        - Redis: Uses redis_prefix and redis_expire to prevent pollution
          in shared database
        - SQLite: No prefix/expire needed - file-based and self-contained
    """
    if redis is not None and sqlite is not None:
        raise ValueError("Cannot specify both redis and sqlite")

    if redis is not None:
        # Setup Redis backend
        _CONFIG["redis"] = redis
        _CONFIG["redis_prefix"] = redis_prefix
        _CONFIG["redis_expire"] = redis_expire
    elif sqlite is not None:
        # Setup SQLite backend
        if isinstance(sqlite, str):
            conn = sqlite3.connect(sqlite)
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
    else:
        raise ValueError("Must specify either redis or sqlite")


# Backward compatibility alias
def setup_sqlite(sqlite: Union[sqlite3.Connection, str]):
    """Deprecated: Use setup() instead."""
    setup(sqlite)


def get_redis_conn() -> Redis:
    return _CONFIG["redis"]


def get_redis_expire() -> int:
    return _CONFIG["redis_expire"]


def get_redis_key(name) -> str:
    return f"{_CONFIG['redis_prefix']}_{name}"


def get_sqlite_conn() -> sqlite3.Connection:
    return _CONFIG["sqlite"]
