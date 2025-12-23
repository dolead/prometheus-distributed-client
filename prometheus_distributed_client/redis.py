import json
import time
from typing import Dict, Iterable, Optional

import prometheus_client
from prometheus_client.samples import Sample
from prometheus_client.utils import floatToGoString
from prometheus_client.values import MutexValue

from .config import get_redis_expire, get_redis_conn, get_redis_key


class ValueClass(MutexValue):
    def __init__(
        self,
        typ,
        metric_name,
        labelnames,
        labelvalues,
        help_text,
        suffix="",
        **kwargs,
    ):
        super().__init__(
            typ,
            metric_name,
            metric_name + suffix,
            labelnames,
            labelvalues,
            help_text,
            **kwargs,
        )
        self.__metric_name = metric_name
        self.__suffix = suffix
        self.__labelnames = labelnames
        self.__labelvalues = labelvalues

    @property
    def _redis_key(self):
        return get_redis_key(self.__metric_name)

    @property
    def _redis_subkey(self):
        labels_json = json.dumps(
            dict(zip(self.__labelnames, self.__labelvalues)), sort_keys=True
        )
        return f"{self.__suffix}:{labels_json}"

    def inc(self, amount):
        conn = get_redis_conn()
        conn.hincrbyfloat(self._redis_key, self._redis_subkey, amount)
        conn.expire(self._redis_key, get_redis_expire())

    def set(self, value, timestamp=None):
        conn = get_redis_conn()
        conn.hset(self._redis_key, self._redis_subkey, value)
        conn.expire(self._redis_key, get_redis_expire())

    def refresh_expire(self):
        get_redis_conn().expire(self._redis_key, get_redis_expire())

    def set_exemplar(self, exemplar):
        raise NotImplementedError()

    def setnx(self, value):
        conn = get_redis_conn()
        conn.hsetnx(self._redis_key, self._redis_subkey, value)
        conn.expire(self._redis_key, get_redis_expire())

    def get(self) -> Optional[float]:
        bvalue = get_redis_conn().hget(self._redis_key, self._redis_subkey)
        if not bvalue:
            return bvalue
        return float(bvalue.decode("utf8"))


class Counter(prometheus_client.Counter):
    def _metric_init(self):
        self._value = ValueClass(
            self._type,
            self._name,
            self._labelnames,
            self._labelvalues,
            self._documentation,
            suffix="_total",
        )
        self._created = ValueClass(
            "gauge",
            self._name,
            self._labelnames,
            self._labelvalues,
            self._documentation,
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
        conn = get_redis_conn()
        key = get_redis_key(self._name)
        for field, value in conn.hgetall(key).items():
            field_str = field.decode("utf8")
            suffix, labels_json = field_str.split(":", 1)
            yield Sample(
                suffix,
                json.loads(labels_json),
                float(value.decode("utf8")),
            )
        conn.expire(key, get_redis_expire())


class Gauge(prometheus_client.Gauge):
    def _metric_init(self):
        self._value = ValueClass(
            self._type,
            self._name,
            self._labelnames,
            self._labelvalues,
            self._documentation,
            suffix="",
            multiprocess_mode=self._multiprocess_mode,
        )

    def _samples(self) -> Iterable[Sample]:
        conn = get_redis_conn()
        key = get_redis_key(self._name)
        for field, value in conn.hgetall(key).items():
            field_str = field.decode("utf8")
            suffix, labels_json = field_str.split(":", 1)
            yield Sample(
                suffix,
                json.loads(labels_json),
                float(value.decode("utf8")),
            )
        conn.expire(key, get_redis_expire())


class Summary(prometheus_client.Summary):
    def _metric_init(self):
        self._count = ValueClass(
            self._type,
            self._name,
            self._labelnames,
            self._labelvalues,
            self._documentation,
            suffix="_count",
        )
        self._sum = ValueClass(
            self._type,
            self._name,
            self._labelnames,
            self._labelvalues,
            self._documentation,
            suffix="_sum",
        )
        self._created = ValueClass(
            "gauge",
            self._name,
            self._labelnames,
            self._labelvalues,
            self._documentation,
            suffix="_created",
        )
        self._created.setnx(time.time())

    def observe(self, amount: float) -> None:
        self._created.refresh_expire()
        return super().observe(amount)

    def _samples(self) -> Iterable[Sample]:
        conn = get_redis_conn()
        key = get_redis_key(self._name)
        for field, value in conn.hgetall(key).items():
            field_str = field.decode("utf8")
            suffix, labels_json = field_str.split(":", 1)
            yield Sample(
                suffix,
                json.loads(labels_json),
                float(value.decode("utf8")),
            )
        conn.expire(key, get_redis_expire())


class Histogram(prometheus_client.Histogram):
    def _metric_init(self):
        self._buckets = []
        self._created = ValueClass(
            "gauge",
            self._name,
            self._labelnames,
            self._labelvalues,
            self._documentation,
            suffix="_created",
        )
        self._created.setnx(time.time())
        bucket_labelnames = self._labelnames + ("le",)
        self._count = ValueClass(
            self._type,
            self._name,
            self._labelnames,
            self._labelvalues,
            self._documentation,
            suffix="_count",
        )
        self._sum = ValueClass(
            self._type,
            self._name,
            self._labelnames,
            self._labelvalues,
            self._documentation,
            suffix="_sum",
        )
        for b in self._upper_bounds:
            self._buckets.append(
                ValueClass(
                    self._type,
                    self._name,
                    bucket_labelnames,
                    self._labelvalues + (floatToGoString(b),),
                    self._documentation,
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
        conn = get_redis_conn()
        key = get_redis_key(self._name)
        for field, value in conn.hgetall(key).items():
            field_str = field.decode("utf8")
            suffix, labels_json = field_str.split(":", 1)
            yield Sample(
                suffix,
                json.loads(labels_json),
                float(value.decode("utf8")),
            )
        conn.expire(key, get_redis_expire())
