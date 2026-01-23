# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`prometheus-distributed-client` is a persistent-storage Prometheus metrics client for short-lived and multiprocess applications. It extends the official `prometheus_client` by replacing in-memory storage with persistent backends (Redis or SQLite), enabling metrics to persist across process boundaries and be served by separate HTTP endpoints.

### Use Cases

This library is ideal for:

1. **Short-lived processes** that cannot expose metrics on a dedicated port (e.g., cron jobs, batch scripts, serverless functions)
2. **Multiprocess applications** where multiple worker processes need to share and aggregate metrics efficiently
3. **Distributed systems** requiring centralized metric collection from multiple instances

### Key Architecture

The library provides two backend implementations (Redis and SQLite) of standard Prometheus metric types (Counter, Gauge, Summary, Histogram) by:
1. Subclassing the official `prometheus_client` metric classes
2. Overriding `_metric_init()` to use custom `ValueClass` instead of `MutexValue`
3. Overriding `_samples()` to read from the backend storage instead of memory

**Storage Format** (prevents desync between metric components):
- **Single key per metric**: All suffixes stored together for atomic expiration
- **Redis**: Hash with fields like `_total:{"label":"value"}`, `_created:{"label":"value"}`
- **SQLite**: Table rows with columns (metric_key, subkey, value) where subkey = `suffix:labels_json`

This ensures all metric components (_total, _created, _sum, etc.) expire together, preventing the desync bug where _created could expire independently.

## Development Commands

### Testing
```bash
# Run all tests
make test

# Run tests directly with unittest
PYTHONPATH=$(pwd) poetry run python -m unittest discover -s tests -p "*_test.py"

# Run tests for specific backend
PYTHONPATH=$(pwd) poetry run python -m unittest tests.redis_test
PYTHONPATH=$(pwd) poetry run python -m unittest tests.sqlite_test

# Run a single test
PYTHONPATH=$(pwd) poetry run python -m unittest tests.redis_test.PDCTestCase.test_counter_no_label
```

**Important for Redis tests**: Tests require a `.redis.json` file in the project root with Redis connection credentials:
```json
{
  "host": "localhost",
  "port": 6379,
  "db": 0
}
```

Redis tests flush the database in `setUp()` and `tearDown()`, so use a dedicated test database.
SQLite tests use in-memory databases (`:memory:`) and don't require external setup.

### Linting
```bash
# Run all lint checks
make lint

# Individual linters
poetry check                                              # Validate pyproject.toml
poetry run pycodestyle --ignore=E126,E127,E128,W503 prometheus_distributed_client/
poetry run black --check --verbose prometheus_distributed_client/
poetry run flake8 prometheus_distributed_client/
poetry run pylint prometheus_distributed_client/ -d I0011,R0901,R0902,R0801,C0111,C0103,C0411,C0415,R0903,R0913,R0914,R0915,R1710,W0613,W0703
```

Note: mypy is commented out in the Makefile.

### Building & Publishing
```bash
make build    # Runs clean, lint, test, then poetry build
make publish  # Builds, publishes to PyPI, creates git tag, pushes tags
```

## Code Organization

```
prometheus_distributed_client/
├── __init__.py   # Exports unified setup() function
├── config.py     # Configuration for both backends
├── redis.py      # Redis backend implementations
└── sqlite.py     # SQLite backend implementations

tests/
├── redis_test.py   # Redis backend tests
└── sqlite_test.py  # SQLite backend tests
```

### Critical Implementation Details

**ValueClass**: Core abstraction that implements metric value storage. Key methods:
- `inc()`: Atomic increments (Redis: `hincrbyfloat`, SQLite: `INSERT ... ON CONFLICT DO UPDATE`)
- `set()`: Absolute value updates with TTL refresh (Redis only)
- `setnx()`: Sets value only if not exists (used for `_created` timestamps)
- `get()`: Retrieves value from storage
- `refresh_expire()`: Extends TTL for entire metric (Redis only, no-op for SQLite)

**Metric Suffixes**: Each metric type stores multiple components:
- Counter: `_total`, `_created`
- Gauge: empty suffix `""`
- Summary: `_count`, `_sum`, `_created`
- Histogram: `_bucket`, `_count`, `_sum`, `_created`

**Storage Format** (critical for preventing desync):
- All suffixes stored in single key/table with format: `suffix:labels_json`
- Redis: `prometheus_counter` → fields `_total:{}`, `_created:{}`
- SQLite: `prometheus_counter` → rows with subkey `_total:{}`, `_created:{}`
- When TTL expires, ALL components expire atomically

**_samples() Implementation**: All metric classes override `_samples()` to:
1. Read all data from single key/table
2. Parse `suffix:labels_json` format
3. Refresh TTL once for entire metric (Redis only)
4. Yield Sample objects for Prometheus exposition format

## Configuration

The library uses a global configuration singleton in `config.py`. Initialize once per application.

**Redis Backend:**
```python
from prometheus_distributed_client import setup
from prometheus_distributed_client.redis import Counter
from redis import Redis

setup(
    redis=Redis(host='localhost', port=6379),
    redis_prefix='prometheus',  # Default: "prometheus"
    redis_expire=3600           # Default: 3600 seconds
)

counter = Counter('my_counter', 'help', registry=REGISTRY)
```

**SQLite Backend:**
```python
from prometheus_distributed_client import setup
from prometheus_distributed_client.sqlite import Counter
import sqlite3

# With file path
setup(sqlite='metrics.db')

# Or with connection object
conn = sqlite3.connect(':memory:')
setup(sqlite=conn)

counter = Counter('my_counter', 'help', registry=REGISTRY)
```

**Key Differences:**
- **Redis TTL**: Required because Redis is typically a central/shared database that could accumulate stale metrics from multiple applications
- **SQLite No TTL**: SQLite is file-based and not shared. Metrics are automatically cleaned up when the file is deleted (e.g., container restart, process cleanup)
- **Redis Prefix parameter**: Used to namespace metrics in Redis (useful for multiple applications sharing one Redis instance or isolation during testing). SQLite doesn't use prefixes since it's self-contained.

## Testing Patterns

Both backends use identical test patterns to ensure compatibility:

**Comparison Tests**: Compare backend metrics against official client using `compate_to_original()`:
1. Perform identical operations on both metric types
2. Generate Prometheus exposition format for both registries
3. Sort and compare line-by-line

**Persistence Tests**: Verify data persists by creating new registry/metric instances and reading from storage.

**Expiration Tests** (Redis only): Verify TTL behavior and that all metric components expire together atomically.

**Time Mocking**: Tests mock `time.time()` (returns `1549444326.4298077`) for deterministic `_created` timestamps. The `test_expire` test (Redis only) temporarily unmocks time to verify actual expiration behavior.

## Code Style

- Black formatting with 79 character line length (target: Python 3.13)
- pycodestyle with ignored errors: E126, E127, E128, W503
- Type hints are used but mypy is currently disabled
