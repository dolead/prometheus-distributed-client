import time
import json
from redis import Redis
import prometheus_client
from prometheus_client.values import MutexValue
from prometheus_client.metrics import MetricWrapperBase
from prometheus_client.utils import floatToGoString


_REDIS_CONN_REGISTRY = {'conn': None}

def set_redis_conn(**kwargs):
    _REDIS_CONN_REGISTRY['conn'] = Redis(**kwargs)
    return _REDIS_CONN_REGISTRY['conn']

def get_redis_conn():
    assert _REDIS_CONN_REGISTRY['conn'] is not None
    return _REDIS_CONN_REGISTRY['conn']


class RedisMetricWrapperBase(MetricWrapperBase):

    def collect(self):
        metric = self._get_metric()
        for suffix in '', '_total', '_sum', '_count', '_created', '_bucket':
            for labels, value in get_redis_conn().hgetall(self._name + suffix).items():
                metric.add_sample(self._name + suffix,
                        json.loads(labels.decode('utf8')),
                        float(value.decode('utf8')))
        return [metric]


class RedisValueClass(MutexValue):

    def __init__(self, typ, metric_name, name, labelnames, labelvalues, **kwargs):
        self.__typ = typ
        self.__metric_name = metric_name
        self.__name = name
        self.__labelnames = labelnames
        self.__labelvalues = labelvalues

    @property
    def _redis_key(self):
        return json.dumps(dict(zip(self.__labelnames, self.__labelvalues)), sort_keys=True)

    def inc(self, amount):
        return get_redis_conn().hincrby(self.__name, self._redis_key, int(amount))

    def set(self, value):
        return get_redis_conn().hset(self.__name, self._redis_key, value)

    def get(self):
        return float(get_redis_conn().hget(self.__name, self._redis_key).decode('utf8'))


class Counter(RedisMetricWrapperBase, prometheus_client.Counter):

    def _metric_init(self):
        self._value = RedisValueClass(self._type, self._name,
                self._name + '_total', self._labelnames, self._labelvalues)
        self._created = time.time()


class Gauge(RedisMetricWrapperBase, prometheus_client.Gauge):

    def _metric_init(self):
        self._value = RedisValueClass(
            self._type, self._name, self._name, self._labelnames, self._labelvalues,
            multiprocess_mode=self._multiprocess_mode
        )


class Summary(prometheus_client.Summary, RedisMetricWrapperBase):

    def _metric_init(self):
        self._count = RedisValueClass(self._type, self._name,
                self._name + '_count', self._labelnames, self._labelvalues)
        self._sum = RedisValueClass(self._type, self._name,
                self._name + '_sum', self._labelnames, self._labelvalues)
        self._created = time.time()


class Histogram(prometheus_client.Histogram, RedisMetricWrapperBase):

    def _metric_init(self):
        self._buckets = []
        self._created = time.time()
        bucket_labelnames = self._labelnames + ('le',)
        self._sum = RedisValueClass(self._type, self._name,
                self._name + '_sum', self._labelnames, self._labelvalues)
        for b in self._upper_bounds:
            self._buckets.append(RedisValueClass(
                self._type,
                self._name,
                self._name + '_bucket',
                bucket_labelnames,
                self._labelvalues + (floatToGoString(b),))
            )
