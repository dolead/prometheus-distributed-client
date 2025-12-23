"""Example usage of SQLite backend for prometheus-distributed-client."""

import sqlite3
from flask import Flask
from prometheus_client import CollectorRegistry, generate_latest

from prometheus_distributed_client import setup
from prometheus_distributed_client.sqlite import Counter, Gauge, Histogram

# Setup SQLite backend
conn = sqlite3.connect("metrics.db")
setup(sqlite=conn)

# Create a registry
REGISTRY = CollectorRegistry()

# Declare metrics
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint"],
    registry=REGISTRY,
)

RESPONSE_TIME = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    registry=REGISTRY,
)

ACTIVE_CONNECTIONS = Gauge(
    "active_connections",
    "Number of active connections",
    registry=REGISTRY,
)

# Example usage in your application
def handle_request(method, endpoint):
    REQUEST_COUNT.labels(method=method, endpoint=endpoint).inc()
    ACTIVE_CONNECTIONS.labels().inc()
    # ... handle request ...
    RESPONSE_TIME.labels(method=method, endpoint=endpoint).observe(0.123)
    ACTIVE_CONNECTIONS.labels().dec()


# Example Flask app to serve metrics
app = Flask(__name__)


@app.route("/metrics")
def metrics():
    return generate_latest(REGISTRY)


if __name__ == "__main__":
    # Simulate some requests
    handle_request("GET", "/api/users")
    handle_request("POST", "/api/users")
    handle_request("GET", "/api/users")

    print("Metrics stored in SQLite!")
    print("\nMetrics output:")
    print(generate_latest(REGISTRY).decode("utf8"))
