from collections import OrderedDict

_all_metrics_defs = OrderedDict()
_all_metrics_backends = {}


def add_metric_def(metric):
    if metric.name in _all_metrics_defs:
        raise RuntimeError("Event %s is already defined" % metric.name)
    _all_metrics_defs[metric.name] = metric
    return True


def add_metric_backend(name, backend_instance):
    _all_metrics_backends[name] = backend_instance


def each_metric_backend():
    yield from _all_metrics_backends.items()
