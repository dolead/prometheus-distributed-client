# Prometheus Distributed Client

[![Build Status](https://travis-ci.org/dolead/prometheus-distributed-client.svg?branch=master)](https://travis-ci.org/dolead/prometheus-distributed-client)
[![Code Climate](https://codeclimate.com/github/dolead/prometheus-distributed-client/badges/gpa.svg)](https://codeclimate.com/github/dolead/prometheus-distributed-client)
[![Coverage Status](https://coveralls.io/repos/github/dolead/prometheus-distributed-client/badge.svg?branch=master)](https://coveralls.io/github/dolead/prometheus-distributed-client?branch=master)

A Prometheus metrics client with persistent storage backends (Redis or SQLite) for short-lived processes and distributed systems.

## Why Use This?

The official [prometheus_client](https://github.com/prometheus/client_python) stores metrics in memory, which doesn't work well for:
- **Short-lived processes** that exit before Prometheus can scrape them or cannot expose a `/metrics` endpoint
- **Multiprocess applications** (web servers with multiple workers, parallel jobs, task queues)
- **Distributed systems** where multiple instances need to share metrics
- **Serverless functions** that need metrics to persist across invocations

This library solves these problems by storing metrics in Redis or SQLite, allowing:
- ✅ Short-lived processes can write metrics without running an HTTP server
- ✅ Multiprocess applications can aggregate metrics efficiently in one place
- ✅ Metrics persist across process boundaries and restarts
- ✅ Multiple processes can update the same metrics atomically
- ✅ Separate HTTP server can serve metrics from storage
- ✅ Automatic TTL/expiration to prevent stale data
- ✅ Full compatibility with Prometheus exposition format

## Installation

```bash
pip install prometheus-distributed-client
```

For Redis backend:
```bash
pip install prometheus-distributed-client redis
```

For SQLite backend (included in Python standard library):
```bash
pip install prometheus-distributed-client
```

## Quick Start

### Redis Backend

```python
from redis import Redis
from prometheus_client import CollectorRegistry, generate_latest
from prometheus_distributed_client import setup
from prometheus_distributed_client.redis import Counter, Gauge, Histogram

# Setup Redis backend
setup(
    redis=Redis(host='localhost', port=6379),
    redis_prefix='myapp',
    redis_expire=3600  # TTL in seconds
)

# Create registry and metrics
REGISTRY = CollectorRegistry()

requests = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint'],
    registry=REGISTRY
)

# Use metrics in your application
requests.labels(method='GET', endpoint='/api/users').inc()

# Serve metrics (in separate process or same)
print(generate_latest(REGISTRY).decode('utf8'))
```

### SQLite Backend

```python
import sqlite3
from prometheus_client import CollectorRegistry, generate_latest
from prometheus_distributed_client import setup_sqlite
from prometheus_distributed_client.sqlite import Counter, Gauge, Histogram

# Setup SQLite backend (no TTL needed)
setup_sqlite(
    'metrics.db',  # or sqlite3.connect(':memory:') for in-memory
    sqlite_prefix='myapp'
)

# Use exactly like Redis backend
REGISTRY = CollectorRegistry()
requests = Counter('http_requests_total', 'Total requests', registry=REGISTRY)
requests.inc()
```

### Key Difference: TTL Behavior

- **Redis**: Uses TTL to prevent pollution in the shared central database
- **SQLite**: No TTL needed - file-based storage is automatically cleaned up when the file is deleted (e.g., container restart)

## Supported Metric Types

All standard Prometheus metric types are supported:

- **Counter**: Monotonically increasing values
- **Gauge**: Values that can go up or down
- **Summary**: Observations with count and sum
- **Histogram**: Observations in configurable buckets

## Architecture

### Storage Format

Both backends use a unified storage format that **prevents component desynchronization**:

**Redis:**
```
Key: prometheus_myapp_requests
Fields:
  _total:{"method":"GET","endpoint":"/api"}    → 42
  _created:{"method":"GET","endpoint":"/api"}  → 1234567890.0
```

**SQLite:**
```sql
metric_key              | subkey                                    | value       | expire_at
------------------------+-------------------------------------------+-------------+-------------
prometheus_myapp_req... | _total:{"method":"GET","endpoint":"/api"} | 42          | 1234571490.0
prometheus_myapp_req... | _created:{"method":"GET","endpoint":"/"...| 1234567890.0| 1234571490.0
```

This design ensures:
- All metric components share the same key/row
- TTL applies to the entire metric atomically
- No desynchronization between `_total`, `_created`, etc.

## Comparison with Alternatives

### vs Pushgateway

The Prometheus [Pushgateway](https://github.com/prometheus/pushgateway) is another solution for short-lived processes, but has limitations:

| Feature | prometheus-distributed-client | Pushgateway |
|---------|------------------------------|-------------|
| Multiple processes updating same metric | ✅ Atomic updates | ❌ Last write wins |
| Automatic metric expiration | ✅ Configurable TTL | ❌ Manual deletion |
| Label-based updates | ✅ Supports all labels | ⚠️ Can overwrite groups |
| Storage backend | Redis or SQLite | In-memory |
| Deployment complexity | Library (no extra service) | Requires separate service |

### vs Multiprocess Mode

For multiprocess applications (e.g., Gunicorn with multiple workers), `prometheus-distributed-client` provides:

- ✅ **Centralized storage**: All metrics in one place (Redis or SQLite)
- ✅ **Simple collection**: Single `/metrics` endpoint to scrape
- ✅ **Atomic updates**: Race-free increments across processes
- ✅ **Easy cleanup**: Automatic TTL-based expiration
- ✅ **Better observability**: Query metrics directly from storage for debugging

## Advanced Usage

### Custom TTL (Redis Only)

```python
# Short TTL for transient metrics
setup(redis, redis_expire=60)  # 1 minute

# Long TTL for important metrics
setup(redis, redis_expire=86400)  # 24 hours

# Note: SQLite doesn't use TTL
```

### Multiple Applications Sharing Backend

```python
# Application 1
setup(redis, redis_prefix='app1')

# Application 2
setup(redis, redis_prefix='app2')

# Metrics are isolated by prefix
```

### Flask Integration

```python
from flask import Flask
from prometheus_client import generate_latest

app = Flask(__name__)

@app.route('/metrics')
def metrics():
    return generate_latest(REGISTRY)
```

### Manual Cleanup (SQLite)

SQLite doesn't use TTL. To manually clean up metrics:

```python
# Clear all metrics
conn = get_sqlite_conn()
cursor = conn.cursor()
cursor.execute("DELETE FROM metrics")
conn.commit()

# Or delete the database file
import os
os.remove('metrics.db')
```

## Testing

The library includes comprehensive test suites for both backends:

```bash
# Install dependencies
poetry install

# Run all tests
make test

# Run specific backend tests
poetry run pytest tests/redis_test.py -v
poetry run pytest tests/sqlite_test.py -v
```

For Redis tests, create `.redis.json`:
```json
{
  "host": "localhost",
  "port": 6379,
  "db": 0
}
```

## Performance Considerations

### Redis
- **Pros**: Atomic operations, high performance, distributed, shared across applications
- **Cons**: Requires Redis server, network latency, needs TTL to prevent pollution
- **Best for**: Distributed systems, high concurrency, shared metrics collection
- **TTL**: Required (default 3600s) to prevent stale metrics in shared database

### SQLite
- **Pros**: No external dependencies, simple deployment, no TTL complexity
- **Cons**: File locking, less concurrent performance, not shared across hosts
- **Best for**: Single-server applications, embedded systems, Docker containers
- **TTL**: Not needed - file cleanup happens on container restart/file deletion

## Development

```bash
# Install dependencies
poetry install

# Run linters
make lint

# Build package
make build

# Publish to PyPI
make publish
```

## License

GPLv3 - See [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Credits

Built by [François Schmidts](https://github.com/jaesivsm) and contributors.

Based on the official [prometheus_client](https://github.com/prometheus/client_python).
