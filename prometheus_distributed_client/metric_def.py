import time
import logging
from enum import Enum
from collections import OrderedDict, defaultdict
from prometheus_client import core as prometheus_core
from prometheus_distributed_client.metrics_registry \
        import add_metric_def, each_metric_backend

logger = logging.getLogger(__name__)
INFINITY = float('inf')


class MetricType(Enum):
    GAUGE = "GAUGE"
    COUNTER = "COUNTER"
    SUMMARY = "SUMMARY"
    HISTOGRAM = "HISTOGRAM"

OBSERVE_METRICS = {MetricType.SUMMARY, MetricType.HISTOGRAM}


def tuplize(d, exclude_keys=None):
    return tuple((key, value) for key, value in d.items()
                 if exclude_keys is None or key not in exclude_keys)



class Metric:

    def __init__(self, name, documentation=None, metric_type=None,
                 labels=None, buckets=None):
        self.created = {}
        self.accepted_backends = []
        self.name = name
        self.documentation = documentation
        self.labels = labels or {}
        self.metric_type = metric_type
        self.buckets = None
        self.samples = []
        if not isinstance(self.metric_type, MetricType):
            self.metric_type = MetricType(self.metric_type)
        # handling buckets for histograms
        if self.metric_type is MetricType.HISTOGRAM:
            assert buckets, "buckets are needed for histogram"
            buckets = [float(b) for b in buckets]
            assert buckets == sorted(buckets), 'buckets not in sorted order'
            if buckets and buckets[-1] != INFINITY:
                buckets.append(INFINITY)
            assert len(buckets) >= 2, 'Must have at least two buckets'
            self.buckets = buckets
        add_metric_def(self)

    @property
    def label_names(self):
        return sorted(self.labels)

    @property
    def bucket_bounds(self):
        assert self.buckets, "no buckets"
        return [('+Inf' if bucket == INFINITY else str(bucket), bucket)
                for bucket in self.buckets]

    def get_bucket_values(self):
        bounds = dict(self.bucket_bounds)
        result = defaultdict(list)
        for labels, value in self.get_values_for_key('bucket', ['le']):
            result[tuplize(labels, {'le'})].append((labels['le'], value))
        for key, buckets_value in result.items():
            result[key] = sorted(buckets_value, key=lambda x: bounds[x[0]])
        return result

    __family_mapping = {MetricType.GAUGE: prometheus_core.GaugeMetricFamily,
            MetricType.COUNTER: prometheus_core.CounterMetricFamily,
            MetricType.SUMMARY: prometheus_core.SummaryMetricFamily,
            MetricType.HISTOGRAM: prometheus_core.HistogramMetricFamily}

    @property
    def metrics_family(self):
        metrics_family_cls = self.__family_mapping[self.metric_type]
        return metrics_family_cls(self.name, self.documentation,
                                  labels=self.label_names)

    # PUSH functions
    def inc(self, value=1, labels=None):
        return self._call_backends('inc', self.name, value, labels)

    def dec(self, value=1, labels=None):
        return self._call_backends('dec', self.name, value, labels)

    def set(self, value, labels=None):
        return self._call_backends('set', self.name, value, labels)

    def set_once(self, value, labels=None):
        return self._call_backends('set_once', self.name, value, labels)

    def observe(self, value, labels=None):
        self._call_backends('inc', self.name + '_count', 1, labels)
        self._call_backends('inc', self.name + '_sum', value, labels)
        tuplized_labels = () if not labels else tuplize(labels)
        if tuplized_labels not in self.created:
            self.created[tuplized_labels] = time.time()
            self._call_backends('set_once', self.name + '_created',
                                self.created[tuplized_labels], labels)
        if self.metric_type is not MetricType.HISTOGRAM:
            return
        labels = labels.copy() if labels else {}
        for name, bound in self.bucket_bounds:
            if value <= bound:
                labels['le'] = name
                self._call_backends('inc', self.name + '_bucket', 1, labels)

    # Utility functions
    @property
    def my_backend(self):
        # For now, only one backend per metric (simplier this way)
        for name, bk_instance in each_metric_backend():
            if not self.accepted_backends or name in self.accepted_backends:
                return bk_instance

    def get_values_for_key(self, suffix='', extra_label_names=None):
        key = ('%s_%s' % (self.name, suffix)) if suffix else self.name
        label_names = self.label_names + (extra_label_names or [])
        values = defaultdict(int)
        for labels, value in self.my_backend.get_each_value(key):
            labels = tuple(map(str, (labels.get(label_name, '')
                                            for label_name in label_names)))
            values[labels] += value
        for sub_key in sorted(values):
            labels = OrderedDict()
            for i, key_value in enumerate(sub_key):
                labels[label_names[i]] = key_value
            yield labels, values[sub_key]

    def get_each_value(self):
        """Returns all the tuples (labels_with_label_values, metric_value)"""
        if not self.my_backend:
            return
        # to avoid doubles, will hash them and sum them before returning them
        if self.metric_type in OBSERVE_METRICS:
            yield from self.get_values_for_key('count')
        else:
            yield from self.get_values_for_key()

    def _call_backends(self, method, name, value, labels):
        logger.debug("[%s] Received method: %s; Backend is: %s",
                     name, method, self.my_backend)
        if self.my_backend:
            getattr(self.my_backend, method)(name, value, labels)
