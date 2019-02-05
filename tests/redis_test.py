import json
import unittest
from redis import Redis
from prometheus_distributed_client import set_redis_conn, Summary, Histogram, Counter
from prometheus_client import CollectorRegistry, generate_latest



class PDCTestCase(unittest.TestCase):

    @staticmethod
    def _get_redis_creds():
        with open('.redis.json') as fd:
            return json.load(fd)

    def _clean(self):
        redis = Redis(**self._get_redis_creds())
        for metric in 'shruberry', 'saysni', 'fleshwound':
            redis.delete(metric)
            redis.delete(metric + '_sum')
            redis.delete(metric + '_total')
            redis.delete(metric + '_count')
            redis.delete(metric + '_created')
            redis.delete(metric + '_bucket')

    def setUp(self):
        self.registry = CollectorRegistry()
        self._clean()
        set_redis_conn(**self._get_redis_creds())

    def tearDown(self):
        self._clean()

    def compate_to_block(self, block):
        for line1, line2 in zip(block.split('\n'),
                generate_latest(self.registry).decode('utf8').split('\n')):
            self.assertEqual(line1, line2)

    def test_counter_no_label(self):
        metric = Counter('shruberry', 'shruberry', registry=self.registry)
        metric.inc()
        self.compate_to_block("""# HELP shruberry_total shruberry
# TYPE shruberry_total counter
shruberry_total 1.0""")
        self.registry = CollectorRegistry()
        metric = Counter('shruberry', 'shruberry', registry=self.registry)
        self.compate_to_block("""# HELP shruberry_total shruberry
# TYPE shruberry_total counter
shruberry_total 1.0""")

    def test_counter_w_label(self):
        metric = Counter('fleshwound', 'fleshwound', ['cross'],
                registry=self.registry)
        metric.labels('').inc()
        metric.labels('eki').inc()
        metric.labels('eki').inc()
        metric.labels('patang').inc()
        self.compate_to_block(
"""# HELP fleshwound_total fleshwound
# TYPE fleshwound_total counter
fleshwound_total{cross=""} 1.0
fleshwound_total{cross="eki"} 2.0
fleshwound_total{cross="patang"} 1.0""")
        self.registry = CollectorRegistry()
        metric = Counter('fleshwound', 'fleshwound', ['cross'],
                registry=self.registry)
        self.compate_to_block(
"""# HELP fleshwound_total fleshwound
# TYPE fleshwound_total counter
fleshwound_total{cross=""} 1.0
fleshwound_total{cross="eki"} 2.0
fleshwound_total{cross="patang"} 1.0""")

    def _test_observe(self, TypeCls, expected_output, **kwargs):
        self.maxDiff = None
        metric = TypeCls('saysni', 'saysni', ['cross'],
                        registry=self.registry, **kwargs)
        for i in range(3):
            metric.labels('').observe(i)
            metric.labels('cross').observe(5 - i)
            metric.labels('label').observe(5 - 2 * i)

        for i in range(3, 5):
            metric.labels('label').observe(5 - 2 * i)
            metric.labels('cross').observe(5 - i)
            metric.labels('').observe(i)

        self.compate_to_block(expected_output)
        self.registry = CollectorRegistry()
        metric = TypeCls('saysni', 'saysni', ['cross'],
                        registry=self.registry, **kwargs)
        self.compate_to_block(expected_output)

    def test_histogram(self):
        expected_output = """# HELP saysni saysni
# TYPE saysni histogram
saysni_sum{cross=""} 10.0
saysni_sum{cross="cross"} 15.0
saysni_sum{cross="label"} 5.0
saysni_bucket{cross="",le="2.5"} 3.0
saysni_bucket{cross="cross",le="+Inf"} 3.0
saysni_bucket{cross="label",le="+Inf"} 2.0
saysni_bucket{cross="label",le="2.5"} 3.0
saysni_bucket{cross="cross",le="2.5"} 2.0
saysni_bucket{cross="",le="+Inf"} 2.0"""
        self._test_observe(Histogram, expected_output, buckets=(2.5,))

    def test_summary(self):
        expected_output = """# HELP saysni saysni
# TYPE saysni summary
saysni_sum{cross=""} 10.0
saysni_sum{cross="cross"} 15.0
saysni_sum{cross="label"} 5.0
saysni_count{cross=""} 5.0
saysni_count{cross="cross"} 5.0
saysni_count{cross="label"} 5.0
"""
        self._test_observe(Summary, expected_output)
