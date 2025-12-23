import json
import time
import unittest
from unittest.mock import patch

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    Summary,
    generate_latest,
)
from prometheus_distributed_client import setup
from prometheus_distributed_client import redis
from redis import Redis


class PDCTestCase(unittest.TestCase):

    @staticmethod
    def _get_redis_creds():
        with open(".redis.json", encoding="utf8") as fd:
            return json.load(fd)

    def _clean(self):
        Redis(**self._get_redis_creds()).flushdb()

    def setUp(self):
        self.registry = CollectorRegistry()
        self.oregistry = CollectorRegistry()
        self._clean()
        setup(Redis(**self._get_redis_creds()))
        self.time_patch = patch("time.time")
        time_mock = self.time_patch.start()
        time_mock.return_value = 1549444326.4298077

    def tearDown(self):
        self.time_patch.stop()
        self._clean()

    def compate_to_original(self):
        def gen_latest(registry):
            return sorted(generate_latest(registry).decode("utf8").split("\n"))

        self.assertEqual(gen_latest(self.oregistry), gen_latest(self.registry))

    def test_counter_no_label(self):
        metric = redis.Counter(
            "shruberry", "shruberry", registry=self.registry
        )
        metric.inc()
        ometric = Counter("shruberry", "shruberry", registry=self.oregistry)
        ometric.inc()
        self.compate_to_original()
        self.registry = CollectorRegistry()
        metric = redis.Counter(
            "shruberry", "shruberry", registry=self.registry
        )
        self.compate_to_original()

    def test_counter_w_label(self):
        self.maxDiff = None
        metric = redis.Counter(
            "fleshwound", "fleshwound", ["cross"], registry=self.registry
        )
        ometric = Counter(
            "fleshwound", "fleshwound", ["cross"], registry=self.oregistry
        )
        for mtrc in metric, ometric:
            mtrc.labels("").inc()
            mtrc.labels("eki").inc()
            mtrc.labels("eki").inc(2)
            mtrc.labels("patang").inc(3)
        self.compate_to_original()
        self.registry = CollectorRegistry()
        metric = redis.Counter(
            "fleshwound", "fleshwound", ["cross"], registry=self.registry
        )
        self.compate_to_original()

    def _test_observe(self, TypeCls, OrigTypeCls, method="observe", **kwargs):
        metric = TypeCls(
            "saysni", "saysni", ["cross"], registry=self.registry, **kwargs
        )
        ometric = OrigTypeCls(
            "saysni", "saysni", ["cross"], registry=self.oregistry, **kwargs
        )
        for i in range(3):
            getattr(metric.labels(""), method)(i * 1.5)
            getattr(ometric.labels(""), method)(i * 1.5)
            getattr(metric.labels("black"), method)(5 - i)
            getattr(ometric.labels("black"), method)(5 - i)
            getattr(metric.labels("knight"), method)(5 - 2 * i)
            getattr(ometric.labels("knight"), method)(5 - 2 * i)

        for i in range(3, 5):
            getattr(metric.labels("black"), method)(5 - 2 * i)
            getattr(ometric.labels("black"), method)(5 - 2 * i)
            getattr(metric.labels("knight"), method)(5 - i)
            getattr(ometric.labels("knight"), method)(5 - i)
            getattr(metric.labels(""), method)(i / 2)
            getattr(ometric.labels(""), method)(i / 2)

        self.compate_to_original()
        self.registry = CollectorRegistry()
        metric = TypeCls(
            "saysni", "saysni", ["cross"], registry=self.registry, **kwargs
        )
        self.compate_to_original()

    def test_histogram(self):
        self._test_observe(redis.Histogram, Histogram, buckets=(0, 2, 4))

    def test_summary(self):
        self._test_observe(redis.Summary, Summary)

    def test_gauge(self):
        self._test_observe(redis.Gauge, Gauge, method="set")

    def test_expire(self):
        setup(Redis(**self._get_redis_creds()), redis_expire=1)
        metric = redis.Counter(
            "shruberry", "shruberry", registry=self.registry
        )
        metric.inc()
        assert 1 == metric._value.get()
        time.sleep(2)
        assert metric._value.get() is None
        assert metric._created.get() is None

    def test_prefix(self):
        setup(Redis(**self._get_redis_creds()), redis_prefix="patang")
        ametric = redis.Counter(
            "shruberry", "shruberry", registry=self.registry
        )
        ametric.inc()
        assert 1 == ametric._value.get()
        assert ametric._created.get() is not None

        setup(Redis(**self._get_redis_creds()), redis_prefix="eki")
        bmetric = redis.Counter(
            "shruberry", "shruberry", registry=self.oregistry
        )
        bmetric.inc(10)

        assert 10 == bmetric._value.get()
        assert bmetric._created.get() is not None

        setup(Redis(**self._get_redis_creds()), redis_prefix="patang")
        assert 1 == ametric._value.get()
        assert ametric._created.get() is not None

    def test_counter_expired_created(self):
        "testing that _created gets refresh on inc"
        setup(Redis(**self._get_redis_creds()), redis_expire=2)
        metric = redis.Counter(
            "shruberry", "shruberry", registry=self.registry
        )
        metric.inc()
        assert 1 == metric._value.get()
        time.sleep(1)
        metric.inc(1)
        time.sleep(1)
        assert metric._value.get() is not None
        assert metric._created.get() is not None

    def test_summary_expired_created(self):
        "testing that _created gets refresh on observe"
        setup(Redis(**self._get_redis_creds()), redis_expire=2)
        metric = redis.Summary(
            "request_duration", "request duration", registry=self.registry
        )
        metric.observe(0.5)
        assert metric._sum.get() == 0.5
        assert metric._count.get() == 1.0
        time.sleep(1)
        metric.observe(1.5)
        time.sleep(1)
        assert metric._sum.get() is not None
        assert metric._count.get() is not None
        assert metric._created.get() is not None

    def test_histogram_expired_created(self):
        "testing that _created gets refresh on observe"
        setup(Redis(**self._get_redis_creds()), redis_expire=2)
        metric = redis.Histogram(
            "request_size", "request size", registry=self.registry
        )
        metric.observe(100)
        assert metric._sum.get() == 100
        assert metric._count.get() == 1.0
        time.sleep(1)
        metric.observe(200)
        time.sleep(1)
        assert metric._sum.get() is not None
        assert metric._count.get() is not None
        assert metric._created.get() is not None
