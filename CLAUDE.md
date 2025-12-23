# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`prometheus-distributed-client` is a Redis-backed Prometheus metrics client for short-lived processes. It extends the official `prometheus_client` by replacing in-memory storage with Redis, enabling metrics to persist across process boundaries and be served by separate HTTP endpoints.

### Key Architecture

The library provides Redis-backed implementations of standard Prometheus metric types (Counter, Gauge, Summary, Histogram) by:
1. Subclassing the official `prometheus_client` metric classes
2. Overriding `_metric_init()` to use custom `ValueClass` instead of `MutexValue`
3. Overriding `_samples()` to read from Redis instead of memory

All metric operations (inc, set, observe) write directly to Redis using hash structures where:
- Hash key: `{redis_prefix}_{metric_name}_{suffix}` (e.g., `prometheus_counter_total`)
- Hash field: JSON-serialized label dict (e.g., `{"label1":"value1"}`)
- Hash value: numeric metric value

Each Redis operation automatically refreshes TTL using the configured `redis_expire` value.

## Development Commands

### Testing
```bash
# Run all tests
make test

# Run tests directly with pytest
PYTHONPATH=$(pwd) poetry run pytest

# Run a single test
PYTHONPATH=$(pwd) poetry run pytest tests/redis_test.py::PDCTestCase::test_counter_no_label
```

**Important**: Tests require a `.redis.json` file in the project root with Redis connection credentials:
```json
{
  "host": "localhost",
  "port": 6379,
  "db": 0
}
```

Tests flush the Redis database in `setUp()` and `tearDown()`, so use a dedicated test database.

### Linting
```bash
# Run all lint checks
make lint

# Individual linters
poetry check                                              # Validate pyproject.toml
poetry run pycodestyle --ignore=E126,E127,E128,W503 prometheus_distributed_client/
poetry run black --check --verbose prometheus_distributed_client/
```

Note: mypy and pylint are commented out in the Makefile.

### Building & Publishing
```bash
make build    # Runs clean, lint, test, then poetry build
make publish  # Builds, publishes to PyPI, creates git tag, pushes tags
```

## Code Organization

```
prometheus_distributed_client/
├── __init__.py   # Exports setup() function
├── config.py     # Global configuration (Redis connection, prefix, TTL)
└── redis.py      # Redis-backed metric implementations (Counter, Gauge, Summary, Histogram)
```

### Critical Implementation Details

**ValueClass** (redis.py:13-73): Core abstraction that implements metric value storage in Redis. Key methods:
- `inc()`: Uses `hincrbyfloat` for atomic increments
- `set()`: Uses `hset` for absolute values
- `setnx()`: Sets value only if not exists (used for `_created` timestamps)
- `get()`: Retrieves and decodes value from Redis
- `refresh_expire()`: Extends TTL without modifying value (critical for `_created` fields)

**Metric Suffixes**: Each metric type uses Redis keys with specific suffixes:
- Counter: `_total`, `_created`
- Gauge: no suffix
- Summary: `_count`, `_sum`, `_created`
- Histogram: `_bucket`, `_count`, `_sum`, `_created`

**TTL Management**: The `_created` suffix requires special handling. When a metric is incremented/observed, `refresh_expire()` must be called on `_created` to keep it in sync with the other suffixes (see Counter.inc():98, Histogram.observe():235).

**_samples() Implementation**: All metric classes override `_samples()` to read all label combinations from Redis hashes, refresh their TTL, and yield Sample objects. This is called when generating the Prometheus exposition format.

## Configuration

The library uses a global configuration singleton in `config.py`. Initialize once per application:

```python
from prometheus_distributed_client import setup
from redis import Redis

setup(
    redis=Redis(host='localhost', port=6379),
    redis_prefix='prometheus',  # Default: "prometheus"
    redis_expire=3600           # Default: 3600 seconds
)
```

**redis_prefix**: Used to namespace metrics in Redis (useful for multiple applications sharing one Redis instance or isolation during testing).

## Testing Patterns

Tests compare output of Redis-backed metrics against the official client's in-memory metrics using `compate_to_original()`:
1. Perform identical operations on both metric types
2. Generate Prometheus exposition format for both registries
3. Sort and compare line-by-line

Tests also verify persistence by creating a new registry/metric instance and confirming data is read from Redis.

Time is mocked in tests (`time.time()` returns `1549444326.4298077`) to ensure deterministic `_created` timestamps.

## Code Style

- Black formatting with 79 character line length (target: Python 3.13)
- pycodestyle with ignored errors: E126, E127, E128, W503
- Type hints are used but mypy is currently disabled
