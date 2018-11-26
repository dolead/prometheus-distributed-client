import json
import unittest
from mock import patch
from redis import Redis
from prometheus_distributed_client import Metric
from prometheus_distributed_client.metrics_registry import (add_metric_backend,
        _all_metrics_defs, _all_metrics_backends)
from prometheus_distributed_client.metric_backends import (
        PrometheusRedisBackend, FlaskUtils)


class PDCTestCase(unittest.TestCase):

    @staticmethod
    def _get_redis_creds():
        with open('.redis.json') as fd:
            return json.load(fd)

    def _clean(self):
        redis = Redis(**self._get_redis_creds())
        for metric in _all_metrics_defs.values():
            redis.delete(metric.name)
            redis.delete(metric.name + '_sum')
            redis.delete(metric.name + '_count')
            redis.delete(metric.name + '_created')
            redis.delete(metric.name + '_bucket')
        _all_metrics_defs.clear()
        _all_metrics_backends.clear()

    def setUp(self):
        self._clean()
        add_metric_backend('PrometheusRedisBackend',
                PrometheusRedisBackend(**self._get_redis_creds()))

    def tearDown(self):
        self._clean()

    def test_export(self):
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

    @patch('time.time')
    def _test_observe(self, type_, expected_output, time_patch,  **kwargs):
        times = (1542994276.7633915, 1542994276.7634358, 1542994276.7634456)
        def time_patch_side_effect():
            yield from times
            while True:  # avoid later on exception
                yield times[-1]
        time_patch.side_effect = time_patch_side_effect().__next__
        self.maxDiff = None
        metric = Metric('saysni', 'saysni', type_,
                        labels={'cross': {}}, **kwargs)
        for i in range(3):
            metric.observe(i)
            metric.observe(5 - i, {'cross': 'cross'})
            metric.observe(5 - 2 * i, {'cross': 'label'})

        for i in range(3, 5):
            metric.observe(5 - 2 * i, {'cross': 'label'})
            metric.observe(5 - i, {'cross': 'cross'})
            metric.observe(i)

        self.assertEqual(expected_output % times,
                         FlaskUtils.flask_to_prometheus([metric]))

    def test_histogram(self):
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
saysni_created{cross=""} %s
saysni_created{cross="cross"} %s
saysni_created{cross="label"} %s
"""
        self._test_observe('HISTOGRAM', expected_output, buckets=(2.5,))

    def test_summary(self):
        expected_output = """# HELP saysni saysni
# TYPE saysni summary
saysni_count{cross=""} 5.0
saysni_sum{cross=""} 10.0
saysni_count{cross="cross"} 5.0
saysni_sum{cross="cross"} 15.0
saysni_count{cross="label"} 5.0
saysni_sum{cross="label"} 5.0
# TYPE saysni_created gauge
saysni_created{cross=""} %s
saysni_created{cross="cross"} %s
saysni_created{cross="label"} %s
"""
        self._test_observe('SUMMARY', expected_output)
