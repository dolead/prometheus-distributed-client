import json
import unittest
from mock import patch
from redis import Redis
from prometheus_distributed_client import (set_redis_conn,
        Summary, Histogram, Counter, Gauge)
from prometheus_client import (CollectorRegistry, generate_latest,
        Summary as OrignalSummary, Histogram as OriginalHistogram,
        Counter as OriginalCounter, Gauge as OriginalGauge)



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
        self.oregistry = CollectorRegistry()
        self._clean()
        set_redis_conn(**self._get_redis_creds())
        self.time_patch = patch('time.time')
        time_mock = self.time_patch.start()
        time_mock.return_value = 1549444326.4298077

    def tearDown(self):
        self.time_patch.stop()
        self._clean()

    def compate_to_original(self):
        def gen_latest(registry):
            return sorted(generate_latest(registry).decode('utf8').split('\n'))
        self.assertEqual(gen_latest(self.oregistry), gen_latest(self.registry))

    def test_counter_no_label(self):
        metric = Counter('shruberry', 'shruberry', registry=self.registry)
        metric.inc()
        ometric = OriginalCounter('shruberry', 'shruberry',
                registry=self.oregistry)
        ometric.inc()
        self.compate_to_original()
        self.registry = CollectorRegistry()
        metric = Counter('shruberry', 'shruberry', registry=self.registry)
        self.compate_to_original()

    def test_counter_w_label(self):
        self.maxDiff = None
        metric = Counter('fleshwound', 'fleshwound', ['cross'],
                registry=self.registry)
        ometric = Counter('fleshwound', 'fleshwound', ['cross'],
                registry=self.oregistry)
        metric.labels('').inc()
        metric.labels('eki').inc()
        metric.labels('eki').inc()
        metric.labels('patang').inc()
        ometric.labels('').inc()
        ometric.labels('eki').inc()
        ometric.labels('eki').inc()
        ometric.labels('patang').inc()
        self.compate_to_original()
        self.registry = CollectorRegistry()
        metric = Counter('fleshwound', 'fleshwound', ['cross'],
                registry=self.registry)
        self.compate_to_original()

    def _test_observe(self, TypeCls, OrigTypeCls, method='observe', **kwargs):
        self.maxDiff = None
        metric = TypeCls('saysni', 'saysni', ['cross'],
                         registry=self.registry, **kwargs)
        ometric = OrigTypeCls('saysni', 'saysni', ['cross'],
                              registry=self.oregistry, **kwargs)
        for i in range(3):
            getattr(metric.labels(''), method)(i)
            getattr(ometric.labels(''), method)(i)
            getattr(metric.labels('black'), method)(5 - i)
            getattr(ometric.labels('black'), method)(5 - i)
            getattr(metric.labels('knight'), method)(5 - 2 * i)
            getattr(ometric.labels('knight'), method)(5 - 2 * i)

        for i in range(3, 5):
            getattr(metric.labels('black'), method)(5 - 2 * i)
            getattr(ometric.labels('black'), method)(5 - 2 * i)
            getattr(metric.labels('knight'), method)(5 - i)
            getattr(ometric.labels('knight'), method)(5 - i)
            getattr(metric.labels(''), method)(i)
            getattr(ometric.labels(''), method)(i)

        self.compate_to_original()
        self.registry = CollectorRegistry()
        metric = TypeCls('saysni', 'saysni', ['cross'],
                         registry=self.registry, **kwargs)
        self.compate_to_original()

    def test_histogram(self):
        self._test_observe(Histogram, OriginalHistogram, buckets=(0, 2, 4))

    def test_summary(self):
        self._test_observe(Summary, OrignalSummary)

    def test_gauge(self):
        self._test_observe(Gauge, OriginalGauge, method='set')
