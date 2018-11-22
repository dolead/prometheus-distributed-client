import json
from collections import defaultdict

from prometheus_client import (generate_latest, CollectorRegistry,
        CONTENT_TYPE_LATEST)

from prometheus_distributed_client.metric_def import MetricType


def tuplize(d, exclude_keys=None):
    return tuple((key, value) for key, value in d.items()
                 if exclude_keys is None or key not in exclude_keys)


class AbstractMetricBackend:
    """ Metric backend interface """

    @staticmethod
    def inc(metric, value, labels=None):
        raise NotImplementedError()

    @staticmethod
    def dev(metric, value, labels=None):
        raise NotImplementedError()

    @staticmethod
    def set(metric, value, labels=None):
        raise NotImplementedError()

    @staticmethod
    def observe(metric, value, labels=None):
        """ Histograms and metrics """
        raise NotImplementedError()


class FlaskUtils:
    """Compose a flask response, for prometheus pull"""

    @staticmethod
    def prometheus_flask_formatter(response):
        from flask import Response
        return Response(response, mimetype="text/plain")

    @staticmethod
    def flask_to_prometheus(metrics):
        metrics_n_vals = {m: m.get_each_value() for m in metrics}
        result = DcmEventsPrometheusExporter.to_http_response(metrics_n_vals)
        return result['body'].decode('utf-8')


class DcmEventsPrometheusExporter:
    """Custom prometheus exporter
        https://github.com/prometheus/client_python#custom-collectors
        https://prometheus.io/docs/instrumenting/writing_exporters/
    """

    @classmethod
    def to_http_response(cls, defs_labels_values):
        """ Returns the body and the headers
            to be exposed to prometheus pull """
        registry = CollectorRegistry()

        # custom exporter formality (have an object with a collect method)
        class Proxy:
            @staticmethod
            def collect():
                # translate to prometheus objects
                yield from cls.to_prometheus_metrics_family(defs_labels_values)
        registry.register(Proxy)
        body = generate_latest(registry)
        return {'headers': {'Content-type': CONTENT_TYPE_LATEST},
                'body': body}

    @classmethod
    def to_prometheus_metrics_family(cls, defs_labels_values):
        for metric, labels_and_values in defs_labels_values.items():
            sums = {}
            if metric.metric_type is MetricType.HISTOGRAM:
                sums = {tuplize(row[0]): row[1]
                        for row in metric.get_values_for_key('sum')}
                buckets = metric.get_bucket_values()

            metrics_family = metric.metrics_family
            # instantiate metric family
            for labels, value in labels_and_values:
                label_values = list(map(str, labels.values()))
                kwargs = {}
                if metric.metric_type is MetricType.HISTOGRAM:
                    metrics_family.add_metric(label_values,
                            buckets=buckets[tuplize(labels, {'le'})],
                            sum_value=sums[tuplize(labels, {'le'})])
                else:
                    metrics_family.add_metric(label_values, value, **kwargs)
            yield metrics_family


class PrometheusCommonBackend:

    @staticmethod
    def labels_dump(labels=None):
        return json.dumps(labels or {}, sort_keys=True)

    @staticmethod
    def labels_load(labels_s):
        return json.loads(labels_s)


class PrometheusPushBackend(PrometheusCommonBackend):
    """ Used for service-level counters, on a multiprocess env
        Therefore, will pre-aggregate metrics in redis before
    """

    def __init__(self, **redis_creds):
        from redis import Redis
        self.redis_conn = Redis(**redis_creds)

    @staticmethod
    def accepts(metric):
        return metric.is_push

    def inc(self, key, value, labels=None):
        return self.redis_conn.hincrby(key, self.labels_dump(labels), value)

    def dec(self, key, value, labels=None):
        return self.redis_conn.hincrby(key, self.labels_dump(labels), -value)

    def set(self, key, value, labels=None):
        return self.redis_conn.hset(key, self.labels_dump(labels), value)

    ## READ methods, to expose stats to Prometheus
    #
    def get_each_value(self, keys):
        for key in keys:
            for labels_s, value in self.redis_conn.hgetall(key).items():
                labels = self.labels_load(labels_s.decode())
                yield labels, float(value.decode())


class PrometheusPullBackend(PrometheusCommonBackend):
    """ Used for service-level pull metrics
    """
    push_gateway_url = None
    prom_handlers_cache = None

    def __init__(self):
        self._all_values = defaultdict(lambda: defaultdict(int))

    @staticmethod
    def accepts(metric):
        return not metric.is_push

    # Methods implemented as WRITE backend
    #
    def inc(self, metric, value=1, labels=None):
        # cache value, expose later through collector
        self._all_values[metric][self.labels_dump(labels)] += value

    def dec(self, metric, value=1, labels=None):
        # cache value, expose later through collector
        self._all_values[metric][self.labels_dump(labels)] -= value

    def set(self, metric, value, labels=None):
        # cache value, expose later through collector
        self._all_values[metric][self.labels_dump(labels)] = value

    def observe(self, metric, value, labels=None):
        return self.set(metric, value, labels)

    ## READ methods, to expose stats to Prometheus
    #
    def get_each_value(self, metrics):
        for metric in metrics:
            for labels_s, value in self._all_values[metric].items():
                labels = self.labels_load(labels_s)
                yield labels, float(value)
