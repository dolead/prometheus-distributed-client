from redis import Redis

_CONFIG = {}


def setup(redis: Redis, prefix: str = "prometheus", expire: int = 3600):
    _CONFIG["redis"] = redis
    _CONFIG["prefix"] = prefix
    _CONFIG["expire"] = expire


def get_redis_conn() -> Redis:
    return _CONFIG["redis"]


def get_expire() -> int:
    return _CONFIG["expire"]


def get_redis_key(name) -> str:
    return f"{_CONFIG['prefix']}_{name}"
