import logging
from enum import Enum
from collections import OrderedDict, defaultdict
from prometheus_distributed_client.metrics_registry \
        import add_metric_def, each_metric_backend

METRIC_NAME_JOINER = "__"


class MetricType(Enum):
    GAUGE = "GAUGE"
    COUNTER = "COUNTER"

logger = logging.getLogger(__name__)


class Metric:

    def __init__(self, name, documentation, metric_type, labels=None):
        self.name = name
        self.documentation = documentation
        self.labels = labels or {}
        self.metric_type = metric_type
        if not isinstance(self.metric_type, MetricType):
            self.metric_type = MetricType(self.metric_type)

        add_metric_def(self)

    @property
    def label_names(self):
        return sorted(self.labels)

    @property
    def is_push(self):
        return self.metric_type is MetricType.COUNTER

    # Functions for PUSH
    #
    def inc(self, value=1, labels=None):
        self._call_backends('inc', value, labels=labels)
        return True

    def dec(self, value=1, labels=None):
        self._call_backends('dec', value, labels=labels)
        return True

    def set(self, value, labels=None):
        self._call_backends('set', value, labels=labels)
        return True

    def observe(self, value, labels=None):
        """ Histograms and metrics """
        self._call_backends('observe', value, labels=labels)
        return True


    # Utility functions
    @property
    def my_backend(self):
        # For now, only one backend per metric (simplier this way)
        for _, bk_instance in each_metric_backend():
            if bk_instance.accepts(self):
                return bk_instance

    def get_each_value(self):
        """Returns all the tuples (labels_with_label_values, metric_value)"""
        if not self.my_backend:
            return
        # to avoid doubles, will hash them and sum them before returning them
        values = defaultdict(int)
        for labels, value in self.my_backend.get_each_value(self):
            key = tuple(map(str, (labels.get(label_name, '')
                                     for label_name in self.label_names)))
            values[key] += value

        for key in sorted(values):
            result_key = OrderedDict()
            for i, key_value in enumerate(key):
                result_key[self.label_names[i]] = key_value
            yield result_key, values[key]

    def _call_backends(self, method, *args, **kwargs):
        logger.debug("[%s] Received method: %s; Backend is: %s",
                     self.name, method, self.my_backend)
        if self.my_backend:
            getattr(self.my_backend, method)(self, *args, **kwargs)
