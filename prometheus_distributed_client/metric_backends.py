import json
from collections import defaultdict

from prometheus_client import (generate_latest, CollectorRegistry,
        CONTENT_TYPE_LATEST)

from prometheus_distributed_client.metric_def import (MetricType,
        tuplize, OBSERVE_METRICS)


class AbstractMetricBackend:
    """ Metric backend interface """

    @staticmethod
    def inc(metric, value, labels=None):
        raise NotImplementedError()

    @staticmethod
    def dec(metric, value, labels=None):
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
            if metric.metric_type in OBSERVE_METRICS:
                sums = {tuplize(row[0]): row[1]
                        for row in metric.get_values_for_key('sum')}
            if metric.metric_type is MetricType.HISTOGRAM:
                buckets = metric.get_bucket_values()

            metrics_family = metric.metrics_family
            # instantiate metric family
            for labels, value in labels_and_values:
                label_values = list(map(str, labels.values()))
                if metric.metric_type is MetricType.HISTOGRAM:
                    tuplized_labels = tuplize(labels, {'le'})
                    metrics_family.add_metric(label_values,
                            buckets=buckets[tuplized_labels],
                            sum_value=sums[tuplized_labels])
                elif metric.metric_type is MetricType.SUMMARY:
                    metrics_family.add_metric(label_values,
                            count_value=value,
                            sum_value=sums[tuplize(labels, {'le'})])
                else:
                    metrics_family.add_metric(label_values, value)
            if metric.metric_type in OBSERVE_METRICS:
                createds = metric.get_values_for_key('created')
                for labels, value in sorted(createds, key=lambda x: x[1]):
                    metrics_family.add_sample(metric.name + '_created',
                            dict(labels), value)

            yield metrics_family


class PrometheusRedisBackend(AbstractMetricBackend):
    """ Used for service-level counters, on a multiprocess env
        Therefore, will pre-aggregate metrics in redis before
    """

    def __init__(self, **redis_creds):
        from redis import Redis
        self.redis_conn = Redis(**redis_creds)

    # translate method
    @staticmethod
    def labels_dump(labels=None):
        return json.dumps(labels or {}, sort_keys=True)

    @staticmethod
    def labels_load(labels_s):
        return json.loads(labels_s)

    # write method
    def inc(self, key, value, labels=None):
        return self.redis_conn.hincrby(key, self.labels_dump(labels), value)

    def dec(self, key, value, labels=None):
        return self.redis_conn.hincrby(key, self.labels_dump(labels), -value)

    def set(self, key, value, labels=None):
        return self.redis_conn.hset(key, self.labels_dump(labels), value)

    def set_once(self, key, value, labels=None):
        return self.redis_conn.hsetnx(key, self.labels_dump(labels), value)

    # read method
    def get_each_value(self, key):
        for labels_s, value in self.redis_conn.hgetall(key).items():
            labels = self.labels_load(labels_s.decode())
            yield labels, float(value.decode())
