import json
from collections import defaultdict

from prometheus_client import generate_latest, CollectorRegistry, CONTENT_TYPE_LATEST
from prometheus_client import core as prom_core

from prometheus_distributed_client.metric_def import MetricType


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
        defs_labels_values = {
            metric: metric.get_each_value()
            for metric in metrics}
        result = DcmEventsPrometheusExporter.to_http_response(defs_labels_values)
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
            # instantiate metric family
            metrics_family_cls = cls._prom_cls(metric)
            metrics_family = metrics_family_cls(
                metric.name,  # name
                metric.name,  # help
                labels=metric.label_names
            )
            for labels_and_value in labels_and_values:
                label_values = list(labels_and_value[0].values())
                label_values = map(str, label_values)
                value = labels_and_value[1]
                metrics_family.add_metric(label_values, value)
            yield metrics_family

    @classmethod
    def _prom_cls(cls, metric):
        return {MetricType.GAUGE: prom_core.GaugeMetricFamily,
                MetricType.COUNTER: prom_core.CounterMetricFamily,
        }[metric.metric_type]


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

    @staticmethod
    def _metric_key(metric):
        return metric.name

    def inc(self, metric, value, labels=None):
        self.redis_conn.hincrby(self._metric_key(metric),
                                self.labels_dump(labels),
                                value)

    def dec(self, metric, value, labels=None):
        self.redis_conn.hincrby(self._metric_key(metric),
                                self.labels_dump(labels),
                                -value)

    def set(self, metric, value, labels=None):
        self.redis_conn.hset(self._metric_key(metric),
                             self.labels_dump(labels),
                             value)

    def observe(self, metric, value, labels=None):
        return self.set(metric, value, labels)

    ## READ methods, to expose stats to Prometheus
    #
    def get_each_value(self, metric):
        key = self._metric_key(metric)
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
    def get_each_value(self, metric):
        for labels_s, value in self._all_values[metric].items():
            labels = self.labels_load(labels_s)
            yield labels, float(value)
