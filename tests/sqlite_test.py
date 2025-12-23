import sqlite3
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
from prometheus_distributed_client import setup_sqlite
from prometheus_distributed_client import sqlite as sqlite_metrics


class PDCTestCase(unittest.TestCase):

    @staticmethod
    def _get_sqlite_conn():
        # Use in-memory database for tests
        return sqlite3.connect(":memory:")

    def _clean(self):
        conn = self.sqlite_conn
        cursor = conn.cursor()
        cursor.execute("DELETE FROM metrics")
        conn.commit()

    def setUp(self):
        self.registry = CollectorRegistry()
        self.oregistry = CollectorRegistry()
        self.sqlite_conn = self._get_sqlite_conn()
        setup_sqlite(self.sqlite_conn)
        self.time_patch = patch("time.time")
        time_mock = self.time_patch.start()
        time_mock.return_value = 1549444326.4298077

    def tearDown(self):
        self.time_patch.stop()
        self._clean()
        self.sqlite_conn.close()

    def compate_to_original(self):
        def gen_latest(registry):
            return sorted(generate_latest(registry).decode("utf8").split("\n"))

        self.assertEqual(gen_latest(self.oregistry), gen_latest(self.registry))

    def test_counter_no_label(self):
        metric = sqlite_metrics.Counter(
            "shruberry", "shruberry", registry=self.registry
        )
        metric.inc()
        ometric = Counter("shruberry", "shruberry", registry=self.oregistry)
        ometric.inc()
        self.compate_to_original()
        self.registry = CollectorRegistry()
        metric = sqlite_metrics.Counter(
            "shruberry", "shruberry", registry=self.registry
        )
        self.compate_to_original()

    def test_counter_w_label(self):
        self.maxDiff = None
        metric = sqlite_metrics.Counter(
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
        metric = sqlite_metrics.Counter(
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
        self._test_observe(
            sqlite_metrics.Histogram, Histogram, buckets=(0, 2, 4)
        )

    def test_summary(self):
        self._test_observe(sqlite_metrics.Summary, Summary)

    def test_gauge(self):
        self._test_observe(sqlite_metrics.Gauge, Gauge, method="set")


    def test_prefix(self):
        setup_sqlite(self.sqlite_conn, sqlite_prefix="patang")
        ametric = sqlite_metrics.Counter(
            "shruberry", "shruberry", registry=self.registry
        )
        ametric.inc()
        assert 1 == ametric._value.get()
        assert ametric._created.get() is not None

        setup_sqlite(self.sqlite_conn, sqlite_prefix="eki")
        bmetric = sqlite_metrics.Counter(
            "shruberry", "shruberry", registry=self.oregistry
        )
        bmetric.inc(10)

        assert 10 == bmetric._value.get()
        assert bmetric._created.get() is not None

        setup_sqlite(self.sqlite_conn, sqlite_prefix="patang")
        assert 1 == ametric._value.get()
        assert ametric._created.get() is not None

