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
        metric = Metric('saysni', 'saysni', 'HISTOGRAM',
                        labels={'cross': {}}, buckets=(2.5,))
        for i in range(5):
            metric.observe(i)
            metric.observe(5 - i, {'cross': 'cross'})
            metric.observe(5 - 2 * i, {'cross': 'label'})

        truc = FlaskUtils.flask_to_prometheus([metric])
        import ipdb
        ipdb.sset_trace()
        self.assertEqual("", FlaskUtils.flask_to_prometheus([metric]))
