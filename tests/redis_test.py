import json
import unittest
from redis import Redis
from prometheus_distributed_client import Metric
from prometheus_distributed_client.metrics_registry import (add_metric_backend,
        _all_metrics_defs, _all_metrics_backends)
from prometheus_distributed_client.metric_backends import (
        PrometheusPullBackend, PrometheusPushBackend, FlaskUtils)


class PDCTestCase(unittest.TestCase):

    @staticmethod
    def _get_redis_creds():
        with open('.redis.json') as fd:
            return json.load(fd)

    def setUp(self):
        add_metric_backend('PrometheusPullBackend', PrometheusPullBackend())

        add_metric_backend('PrometheusPushBackend',
                PrometheusPushBackend(**self._get_redis_creds()))

    def tearDown(self):
        redis = Redis(**self._get_redis_creds())
        for metric in _all_metrics_defs.values():
            redis.delete(metric.name)
        _all_metrics_defs.clear()
        _all_metrics_backends.clear()

    def _test_export(self):
        metric1 = Metric('shruberry', 'shruberry', 'COUNTER')
        metric2 = Metric('fleshwound', 'fleshwound', 'COUNTER', {'cross': {}})
        metric1.inc()
        metric2.inc()
        metric2.inc(labels={'cross': 'eki'})
        metric2.inc(labels={'cross': 'eki'})
        metric2.inc(labels={'cross': 'patang'})
        self.assertEqual(
"""# HELP shruberry_total shruberry
# TYPE shruberry_total counter
shruberry_total 1.0
""", FlaskUtils.flask_to_prometheus([metric1]))
        self.assertEqual(
"""# HELP fleshwound_total fleshwound
# TYPE fleshwound_total counter
fleshwound_total{cross=""} 1.0
fleshwound_total{cross="eki"} 2.0
fleshwound_total{cross="patang"} 1.0
""", FlaskUtils.flask_to_prometheus([metric2]))

    def test_histogram(self):
        self.maxDiff = None
        expected_output = """# HELP saysni saysni
# TYPE saysni histogram
saysni_bucket{cross="",le="2.5"} 3.0
saysni_bucket{cross="",le="+Inf"} 5.0
saysni_count{cross=""} 5.0
saysni_sum{cross=""} 10.0
saysni_bucket{cross="cross",le="2.5"} 2.0
saysni_bucket{cross="cross",le="+Inf"} 5.0
saysni_count{cross="cross"} 5.0
saysni_sum{cross="cross"} 15.0
saysni_bucket{cross="label",le="2.5"} 3.0
saysni_bucket{cross="label",le="+Inf"} 5.0
saysni_count{cross="label"} 5.0
saysni_sum{cross="label"} 5.0
# TYPE saysni_created gauge
saysni_created{cross=""} 1542994276.7633915
saysni_created{cross="cross"} 1542994276.7634358
saysni_created{cross="label"} 1542994276.7634456
"""
        metric = Metric('saysni', 'saysni', 'HISTOGRAM',
                        labels={'cross': {}}, buckets=(2.5,))
        for i in range(5):
            metric.observe(i)
            metric.observe(5 - i, {'cross': 'cross'})
            metric.observe(5 - 2 * i, {'cross': 'label'})

        self.assertEqual(expected_output, FlaskUtils.flask_to_prometheus([metric]))
