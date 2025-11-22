from redis import Redis

_CONFIG = {}


def setup(
    redis: Redis, redis_prefix: str = "prometheus", redis_expire: int = 3600
):
    _CONFIG["redis"] = redis
    _CONFIG["redis_prefix"] = redis_prefix
    _CONFIG["redis_expire"] = redis_expire


def get_redis_conn() -> Redis:
    return _CONFIG["redis"]


def get_redis_expire() -> int:
    return _CONFIG["redis_expire"]


def get_redis_key(name) -> str:
    return f"{_CONFIG['redis_prefix']}_{name}"
