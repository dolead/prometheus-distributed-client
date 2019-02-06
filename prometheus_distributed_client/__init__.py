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


class RedisValueClass(MutexValue):

    def __init__(self, typ, metric_name, name, labelnames, labelvalues, **kwargs):
        super().__init__(typ, metric_name, name, labelnames, labelvalues, **kwargs)
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

    def setnx(self, value):
        return get_redis_conn().hsetnx(self.__name, self._redis_key, value)

    def get(self):
        pass


class Counter(prometheus_client.Counter):

    def _metric_init(self):
        self._value = RedisValueClass(self._type, self._name,
                self._name + '_total', self._labelnames, self._labelvalues)
        self._created = RedisValueClass('gauge', self._name,
                self._name + '_created', self._labelnames, self._labelvalues)
        self._created.setnx(time.time())

    def _multi_samples(self):
        for suffix in '_total', '_created':
            for labels, value in get_redis_conn().hgetall(self._name + suffix).items():
                yield (suffix,
                       json.loads(labels.decode('utf8')),
                       float(value.decode('utf8')))

    _child_samples = _multi_samples


class Gauge(prometheus_client.Gauge):

    def _metric_init(self):
        self._value = RedisValueClass(
            self._type, self._name, self._name, self._labelnames, self._labelvalues,
            multiprocess_mode=self._multiprocess_mode
        )

    def _multi_samples(self):
        for labels, value in get_redis_conn().hgetall(self._name).items():
            yield ('', json.loads(labels.decode('utf8')),
                    float(value.decode('utf8')))

    _child_samples = _multi_samples


class Summary(prometheus_client.Summary):

    def _metric_init(self):
        self._count = RedisValueClass(self._type, self._name,
                self._name + '_count', self._labelnames, self._labelvalues)
        self._sum = RedisValueClass(self._type, self._name,
                self._name + '_sum', self._labelnames, self._labelvalues)
        self._created = RedisValueClass('gauge', self._name,
                self._name + '_created', self._labelnames, self._labelvalues)
        self._created.setnx(time.time())

    def _multi_samples(self):
        for suffix in '_count', '_sum', '_created':
            for labels, value in get_redis_conn().hgetall(self._name + suffix).items():
                yield (suffix, json.loads(labels.decode('utf8')),
                       float(value.decode('utf8')))

    _child_samples = _multi_samples


class Histogram(prometheus_client.Histogram):

    def _metric_init(self):
        self._buckets = []
        self._created = RedisValueClass('gauge', self._name,
                self._name + '_created', self._labelnames, self._labelvalues)
        self._created.setnx(time.time())
        bucket_labelnames = self._labelnames + ('le',)
        self._count = RedisValueClass(self._type, self._name,
                self._name + '_count', self._labelnames, self._labelvalues)
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

    def observe(self, amount):
        '''Observe the given amount.'''
        self._sum.inc(amount)
        for i, bound in enumerate(self._upper_bounds):
            if amount <= bound:
                self._buckets[i].inc(1)
            else:
                self._buckets[i].inc(0)
        self._count.inc(1)


    def _multi_samples(self):
        conn = get_redis_conn()
        for suffix in '_sum', '_created', '_bucket', '_count':
            for labels, value in conn.hgetall(self._name + suffix).items():
                labels = json.loads(labels.decode('utf8'))
                value = float(value.decode('utf8'))
                yield (suffix, labels, value)
