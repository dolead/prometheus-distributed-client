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
        name,
        labelnames,
        labelvalues,
        help_text,
        **kwargs,
    ):
        super().__init__(
            typ,
            metric_name,
            name,
            labelnames,
            labelvalues,
            help_text,
            **kwargs,
        )
        self.__name = name
        self.__labelnames = labelnames
        self.__labelvalues = labelvalues

    @property
    def _redis_subkey(self):
        return json.dumps(
            dict(zip(self.__labelnames, self.__labelvalues)), sort_keys=True
        )

    def inc(self, amount):
        conn = get_redis_conn()
        redis_key = get_redis_key(self.__name)
        conn.hincrbyfloat(redis_key, self._redis_subkey, amount)
        conn.expire(redis_key, get_redis_expire())

    def set(self, value, timestamp=None):
        conn = get_redis_conn()
        redis_key = get_redis_key(self.__name)
        conn.hset(redis_key, self._redis_subkey, value)
        conn.expire(redis_key, get_redis_expire())

    def refresh_expire(self):
        get_redis_conn().expire(get_redis_key(self.__name), get_redis_expire())

    def set_exemplar(self, exemplar):
        raise NotImplementedError()

    def setnx(self, value):
        conn = get_redis_conn()
        redis_key = get_redis_key(self.__name)
        conn.hsetnx(redis_key, self._redis_subkey, value)
        conn.expire(redis_key, get_redis_expire())

    def get(self) -> Optional[float]:
        redis_key = get_redis_key(self.__name)
        bvalue = get_redis_conn().hget(redis_key, self._redis_subkey)
        if not bvalue:
            return bvalue
        return float(bvalue.decode("utf8"))


class Counter(prometheus_client.Counter):
    def _metric_init(self):
        self._value = ValueClass(
            self._type,
            self._name,
            self._name + "_total",
            self._labelnames,
            self._labelvalues,
            self._documentation,
        )
        self._created = ValueClass(
            "gauge",
            self._name,
            self._name + "_created",
            self._labelnames,
            self._labelvalues,
            self._documentation,
        )
        self._created.setnx(time.time())

    def inc(
        self, amount: float = 1, exemplar: Optional[Dict[str, str]] = None
    ) -> None:
        self._created.refresh_expire()
        return super().inc(amount, exemplar)

    def reset(self) -> None:
        self._value.set(0)
        self._created.set(time.time())

    def _samples(self) -> Iterable[Sample]:
        conn = get_redis_conn()
        expire = get_redis_expire()
        for suffix in "_total", "_created":
            key = get_redis_key(self._name) + suffix
            for labels, value in conn.hgetall(key).items():
                yield Sample(
                    suffix,
                    json.loads(labels.decode("utf8")),
                    float(value.decode("utf8")),
                )
            conn.expire(key, expire)


class Gauge(prometheus_client.Gauge):
    def _metric_init(self):
        self._value = ValueClass(
            self._type,
            self._name,
            self._name,
            self._labelnames,
            self._labelvalues,
            self._documentation,
            multiprocess_mode=self._multiprocess_mode,
        )

    def _samples(self) -> Iterable[Sample]:
        conn = get_redis_conn()
        expire = get_redis_expire()
        key = get_redis_key(self._name)
        for labels, value in conn.hgetall(key).items():
            yield Sample(
                "",
                json.loads(labels.decode("utf8")),
                float(value.decode("utf8")),
            )
            conn.expire(key, expire)


class Summary(prometheus_client.Summary):
    def _metric_init(self):
        self._count = ValueClass(
            self._type,
            self._name,
            self._name + "_count",
            self._labelnames,
            self._labelvalues,
            self._documentation,
        )
        self._sum = ValueClass(
            self._type,
            self._name,
            self._name + "_sum",
            self._labelnames,
            self._labelvalues,
            self._documentation,
        )
        self._created = ValueClass(
            "gauge",
            self._name,
            self._name + "_created",
            self._labelnames,
            self._labelvalues,
            self._documentation,
        )
        self._created.setnx(time.time())

    def _samples(self) -> Iterable[Sample]:
        conn = get_redis_conn()
        expire = get_redis_expire()
        for suffix in "_count", "_sum", "_created":
            key = get_redis_key(self._name) + suffix
            for labels, value in conn.hgetall(key).items():
                value = float(value.decode("utf8"))
                yield Sample(suffix, json.loads(labels.decode("utf8")), value)
            conn.expire(key, expire)


class Histogram(prometheus_client.Histogram):
    def _metric_init(self):
        self._buckets = []
        self._created = ValueClass(
            "gauge",
            self._name,
            self._name + "_created",
            self._labelnames,
            self._labelvalues,
            self._documentation,
        )
        self._created.setnx(time.time())
        bucket_labelnames = self._labelnames + ("le",)
        self._count = ValueClass(
            self._type,
            self._name,
            self._name + "_count",
            self._labelnames,
            self._labelvalues,
            self._documentation,
        )
        self._sum = ValueClass(
            self._type,
            self._name,
            self._name + "_sum",
            self._labelnames,
            self._labelvalues,
            self._documentation,
        )
        for b in self._upper_bounds:
            self._buckets.append(
                ValueClass(
                    self._type,
                    self._name,
                    self._name + "_bucket",
                    bucket_labelnames,
                    self._labelvalues + (floatToGoString(b),),
                    self._documentation,
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
        expire = get_redis_expire()
        for suffix in "_sum", "_created", "_bucket", "_count":
            key = get_redis_key(self._name) + suffix
            for labels, value in conn.hgetall(key).items():
                labels = json.loads(labels.decode("utf8"))
                value = float(value.decode("utf8"))
                yield Sample(suffix, labels, value)
            conn.expire(key, expire)
