import json
import time
from typing import Dict, Iterable, Optional

import prometheus_client
from prometheus_client.samples import Sample
from prometheus_client.utils import floatToGoString
from prometheus_client.values import MutexValue

from .config import get_sqlite_conn


class ValueClass(MutexValue):
    def __init__(
        self,
        typ,
        metric_name,
        labelnames,
        labelvalues,
        **kwargs,
    ):
        super().__init__(
            typ,
            metric_name,
            metric_name + kwargs.get("suffix", ""),
            labelnames,
            labelvalues,
            **kwargs,
        )
        self.__metric_name = metric_name
        self.__suffix = kwargs.get("suffix", "")
        self.__labelnames = labelnames
        self.__labelvalues = labelvalues

    @property
    def _sqlite_key(self):
        return self.__metric_name

    @property
    def _sqlite_subkey(self):
        labels_json = json.dumps(
            dict(zip(self.__labelnames, self.__labelvalues)), sort_keys=True
        )
        return f"{self.__suffix}:{labels_json}"

    def _execute(self, query, params):
        conn = get_sqlite_conn()
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        return cursor

    def inc(self, amount):
        metric_key = self._sqlite_key
        subkey = self._sqlite_subkey

        # SQLite doesn't have atomic float increment, so we need to
        # do it in a transaction
        self._execute(
            """
            INSERT INTO metrics (metric_key, subkey, value)
            VALUES (?, ?, ?)
            ON CONFLICT(metric_key, subkey) DO UPDATE SET
                value = value + ?
            """,
            (metric_key, subkey, amount, amount),
        )

    def set(self, value, timestamp=None):
        metric_key = self._sqlite_key
        subkey = self._sqlite_subkey

        self._execute(
            """
            INSERT INTO metrics (metric_key, subkey, value)
            VALUES (?, ?, ?)
            ON CONFLICT(metric_key, subkey) DO UPDATE SET
                value = ?
            """,
            (metric_key, subkey, value, value),
        )

    def refresh_expire(self):
        # No-op for SQLite - no TTL needed
        pass

    def set_exemplar(self, exemplar):
        raise NotImplementedError()

    def setnx(self, value):
        metric_key = self._sqlite_key
        subkey = self._sqlite_subkey

        self._execute(
            """
            INSERT INTO metrics (metric_key, subkey, value)
            VALUES (?, ?, ?)
            ON CONFLICT(metric_key, subkey) DO NOTHING
            """,
            (metric_key, subkey, value),
        )

    def get(self) -> Optional[float]:
        conn = get_sqlite_conn()
        cursor = conn.cursor()
        metric_key = self._sqlite_key
        subkey = self._sqlite_subkey

        cursor.execute(
            """
            SELECT value FROM metrics
            WHERE metric_key = ? AND subkey = ?
            """,
            (metric_key, subkey),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return float(row[0])


class Counter(prometheus_client.Counter):
    def _metric_init(self):
        self._value = ValueClass(
            self._type,
            self._name,
            self._labelnames,
            self._labelvalues,
            help_text=self._documentation,
            suffix="_total",
        )
        self._created = ValueClass(
            "gauge",
            self._name,
            self._labelnames,
            self._labelvalues,
            help_text=self._documentation,
            suffix="_created",
        )
        self._created.setnx(time.time())

    def inc(
        self, amount: float = 1, exemplar: Optional[Dict[str, str]] = None
    ) -> None:
        self._created.setnx(time.time())
        self._created.refresh_expire()
        return super().inc(amount, exemplar)

    def reset(self) -> None:
        self._value.set(0)
        self._created.set(time.time())

    def _samples(self) -> Iterable[Sample]:
        conn = get_sqlite_conn()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT subkey, value FROM metrics
            WHERE metric_key = ?
            """,
            (self._name,),
        )

        for row in cursor.fetchall():
            subkey, value = row
            suffix, labels_json = subkey.split(":", 1)
            yield Sample(
                suffix,
                json.loads(labels_json),
                float(value),
            )


class Gauge(prometheus_client.Gauge):
    def _metric_init(self):
        self._value = ValueClass(
            self._type,
            self._name,
            self._labelnames,
            self._labelvalues,
            help_text=self._documentation,
            suffix="",
        )

    def _samples(self) -> Iterable[Sample]:
        conn = get_sqlite_conn()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT subkey, value FROM metrics
            WHERE metric_key = ?
            """,
            (self._name,),
        )

        for row in cursor.fetchall():
            subkey, value = row
            suffix, labels_json = subkey.split(":", 1)
            yield Sample(
                suffix,
                json.loads(labels_json),
                float(value),
            )


class Summary(prometheus_client.Summary):
    def _metric_init(self):
        self._count = ValueClass(
            self._type,
            self._name,
            self._labelnames,
            self._labelvalues,
            help_text=self._documentation,
            suffix="_count",
        )
        self._sum = ValueClass(
            self._type,
            self._name,
            self._labelnames,
            self._labelvalues,
            help_text=self._documentation,
            suffix="_sum",
        )
        self._created = ValueClass(
            "gauge",
            self._name,
            self._labelnames,
            self._labelvalues,
            help_text=self._documentation,
            suffix="_created",
        )
        self._created.setnx(time.time())

    def observe(self, amount: float) -> None:
        self._created.refresh_expire()
        return super().observe(amount)

    def _samples(self) -> Iterable[Sample]:
        conn = get_sqlite_conn()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT subkey, value FROM metrics
            WHERE metric_key = ?
            """,
            (self._name,),
        )

        for row in cursor.fetchall():
            subkey, value = row
            suffix, labels_json = subkey.split(":", 1)
            yield Sample(
                suffix,
                json.loads(labels_json),
                float(value),
            )


class Histogram(prometheus_client.Histogram):
    def _metric_init(self):
        self._buckets = []
        self._created = ValueClass(
            "gauge",
            self._name,
            self._labelnames,
            self._labelvalues,
            help_text=self._documentation,
            suffix="_created",
        )
        self._created.setnx(time.time())
        bucket_labelnames = self._labelnames + ("le",)
        self._count = ValueClass(
            self._type,
            self._name,
            self._labelnames,
            self._labelvalues,
            help_text=self._documentation,
            suffix="_count",
        )
        self._sum = ValueClass(
            self._type,
            self._name,
            self._labelnames,
            self._labelvalues,
            help_text=self._documentation,
            suffix="_sum",
        )
        for b in self._upper_bounds:
            self._buckets.append(
                ValueClass(
                    self._type,
                    self._name,
                    bucket_labelnames,
                    self._labelvalues + (floatToGoString(b),),
                    help_text=self._documentation,
                    suffix="_bucket",
                )
            )

    def observe(
        self, amount: float, exemplar: Optional[Dict[str, str]] = None
    ) -> None:
        """Observe the given amount."""
        self._sum.inc(amount)
        for i, bound in enumerate(self._upper_bounds):
            if amount <= bound:
                self._buckets[i].inc(1)
            else:
                self._buckets[i].inc(0)
        self._count.inc(1)
        self._created.refresh_expire()

    def _samples(self) -> Iterable[Sample]:
        conn = get_sqlite_conn()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT subkey, value FROM metrics
            WHERE metric_key = ?
            """,
            (self._name,),
        )

        for row in cursor.fetchall():
            subkey, value = row
            suffix, labels_json = subkey.split(":", 1)
            yield Sample(
                suffix,
                json.loads(labels_json),
                float(value),
            )
