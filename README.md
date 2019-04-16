[![Build Status](https://travis-ci.org/dolead/prometheus-distributed-client.svg?branch=master)](https://travis-ci.org/dolead/prometheus-distributed-client)
[![Code Climate](https://codeclimate.com/github/dolead/prometheus-distributed-client/badges/gpa.svg)](https://codeclimate.com/github/dolead/prometheus-distributed-client)
[![Coverage Status](https://coveralls.io/repos/github/dolead/prometheus-distributed-client/badge.svg?branch=master)](https://coveralls.io/github/dolead/prometheus-distributed-client?branch=master)

# Prometheus Distributed Client

### Purpose and principle

```prometheus-distributed-client``` is aimed at shorted lived process that can expose [Prometheus](https://prometheus.io/) metrics through HTTP.

### Advantages over Pushgateway

The prometheus project provides several ways of publishing metrics. Either you publish them directly like the [official client](https://github.com/prometheus/client_python) allows you to do, or you push them to a [pushgateway](https://github.com/prometheus/pushgateway).

The first method implies you've got to keep your metrics in-memory and publishs them over http.
The second method implies that you'll either have a pushgateway per process or split your metrics over all your processes to avoid overwriting your existing pushed metrics.

```prometheus-distributed-client``` allows you to have your short lived process push metrics to a database and have another process serving them over HTTP. One of the perks of that approach is that you keep consistency over concurrent calls. (Making multiple counter increment from multiple process will be acknowledge correctly by the database).

### Code examples

```prometheus-distributed-client``` uses the base of the [official client](https://github.com/prometheus/client_python) but replaces all write and read operation by database call.

#### Declaring and using metrics

```python
from prometheus-distributed-client import set_redis_conn, Counter, Gauge
# we use the official clients internal architecture
from prometheus_client import CollectorRegistry

# set your own registry
REGISTRY = CollectorRegistry()
# declare metrics from prometheus-distributed-client
COUNTER = Counter('counter_metric_name', 'metric documentation',
                  [labels], registry=REGISTRY)
GAUGE = Gauge('gauge_metric_name', 'metric documentation',
                  [labels], registry=REGISTRY)

# increment a counter and set a value for a gauge
COUNTER.labels('label_value').inc()
GAUGE.labels('other_label_value').set(12)
```

### Serving the metrics

```prometheus-distributed-client``` use the registry system from the official client and is de facto compatible with it. If you want to register regular metrics alongside the one from ```prometheus-distributed-client``` it is totally feasible.
Here is a little example of how to serv metrics from ```prometheus-distributed-client```, but you can also refer to the [documentation of the official client](https://github.com/prometheus/client_python#exporting).

```python
# with flask

from flask import Flask
from prometheus_client import generate_latest
# get the registry you declared your metrics in
from metrics import REGISTRY

app = Flask()

@app.route('/metrics')
def metrics():
    return generate_latest(REGISTRY)
```
