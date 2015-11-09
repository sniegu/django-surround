from __future__ import absolute_import
from redis_cache import get_redis_connection
import pickle
import redis
from django.conf import settings
from surround.django.utils import CacheKey
from surround.django import execution
import datetime
from redis import WatchError

from surround.django.logging import setupModuleLogger
setupModuleLogger(globals())

def set_pickled(self, key, value):
    self.set(key, pickle.dumps(value))

def get_pickled(self, key):
    obj = self.get(key)
    if obj is None:
        return None
    return pickle.loads(obj)

redis.StrictRedis.set_pickled = set_pickled
redis.StrictRedis.get_pickled = get_pickled

def get_connection():
    connection = get_redis_connection('redis')
    return connection

# make_key cannot be used here, since the key is already in its final shape
def purge(key_mask):
    debug('purging redis: %s', key_mask)
    r = get_connection()
    if '*' in key_mask:
        count = 0
        for k in r.keys(key_mask):
            r.delete(k)
            count += 1
        return count
    else:
        return r.delete(key_mask)





class CommonCacheProxy(object):

    def __init__(self, func, timeout, key, exceptions_include):
        self.func = func
        self.timeout = timeout
        self.key = key
        self.exceptions_include = exceptions_include

    def _key(self, args, kwargs):
        return self.key(*args, **kwargs)


    def purge(self, *args, **kwargs):
        return self.delete(*args, **kwargs)

    def force(self, *args, **kwargs):
        self.delete(*args, **kwargs)
        return self(*args, **kwargs)

    def _multicall(self, multi):
        from surround.django import coroutine
        return coroutine.execute_all(self.func, multi)

    def multi(self, multi):
        return self._multicall(multi)

    def single(self, parameters):
        return execution.execute(self, parameters)

    def compute_cache_timeout(self, entry):
        if entry.exception is None:
            return self.timeout
        if self.exceptions_include is not None:
            for exception_types, timeout in self.exceptions_include:
                if isinstance(entry.exception, exception_types):
                    return timeout
        return None

    def __str__(self):
        return '%s(%s)' % (self.__class__.__name__, self.func.__name__)



class CacheProxy(CommonCacheProxy):

    def _load_entry(self, pickled_entry):
        return pickle.loads(pickled_entry)

    def _store_entry(self, r, key, entry):
        timeout = self.compute_cache_timeout(entry)
        if timeout is not None:
            r.set(key, pickle.dumps(entry))
            r.expire(key, timeout)


    def multi(self, multi):
        results = {}
        keys = {name: self._key(parameters.args, parameters.kwargs) for name, parameters in multi.items()}

        r = get_connection()
        pipe = r.pipeline()
        for key in keys.values():
            pipe.get(key)
        pickled_entries = pipe.execute()

        hits = 0
        misses = 0

        for name, pickled_entry in zip(keys.keys(), pickled_entries):
            if pickled_entry is not None:
                results[name] = self._load_entry(pickled_entry)
                del multi[name]
                hits += 1


        missed_results = self._multicall(multi)

        for name, entry in missed_results.results.items():
            misses += 1
            self._store_entry(r, keys[name], entry)

        results.update(missed_results.results)

        debug('called multi on %s: %d hits, %d misses, %d in total', self, hits, misses, hits + misses)

        return execution.MultiResult(results)

    def __call__(self, *args, **kwargs):
        r = get_connection()
        key = self._key(args, kwargs)
        pickled_entry = r.get(key)
        if pickled_entry is not None:
            return self._load_entry(pickled_entry).return_result()

        result = execution.execute(self.func, execution.Parameters(args, kwargs))
        self._store_entry(r, key, result)

        return result.return_result()

    def delete(self, *args, **kwargs):
        key = self._key(args, kwargs)
        deleted = purge(key)
        debug("delete of key %s resulted in %s objects removed", key, deleted)
        return deleted > 0

class DummyCacheProxy(CommonCacheProxy):

    def __call__(self, *args, **kwargs):
        return execution.execute(self.func, execution.Parameters(args, kwargs)).return_result()

    def delete(self, *args, **kwargs):
        return False


def cache_result(timeout, key, exceptions_include=None):

    def decorator(func):
        return CacheProxy(func, timeout, key, exceptions_include)

    return decorator


def dummy_cache_result(timeout, key, exceptions_include=None):

    def decorator(func):
        return DummyCacheProxy(func, timeout, key, exceptions_include)

    return decorator


class KeyNotFoundException(redis.RedisError):
    pass


class Notification(object):
    def __init__(self, _timeout, _failure, _comment=None, _repeat_timeout=None):
        self._timeout = datetime.timedelta(seconds=_timeout)
        self._repeat_timeout = None if _repeat_timeout is None else datetime.timedelta(seconds=_repeat_timeout)
        self._failure = _failure
        self._success = None
        self._name = _failure.__name__
        self._comment = _comment
        self._label = 'notified_' + self._name

    def success(self, _success):
        self._success = _success

    @property
    def comment(self):
        return self._comment


def notification(timeout, repeat_timeout=None, comment=None):
    def wrapper(failure):
        n = Notification(_timeout=timeout, _repeat_timeout = repeat_timeout, _failure=failure, _comment=comment)
        # cls._notifications.append(n)
        return n
    return wrapper


class ReferenceMonitorMetaclass(type):
    def __new__(meta, name, bases, attrs):
        assert (len(bases) == 1 and (bases[0] == object or bases[0] == ReferenceMonitor)), "multiple and indirect inheritance of ReferenceMonitor is not (yet) supported"
        _notifications = []
        for attr in attrs.values():
            if isinstance(attr, Notification):
                _notifications.append(attr)
        attrs['_reference_monitor_notifications'] = _notifications

        return super(ReferenceMonitorMetaclass, meta).__new__(meta, name, bases, attrs)

class ReferenceMonitor(object):

    datetime_format = '%Y-%m-%dT%H:%M:%S'
    failure_label = 'failure'
    success_label = 'success'

    __metaclass__ = ReferenceMonitorMetaclass

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self._key_value = self.key(*self.args, **self.kwargs)

    def _get_moment(self, r, label):
        m = r.hget(self._key_value, label)
        if m is None:
            return None
        return datetime.datetime.strptime(m, self.datetime_format)

    def _set_moment(self, r, label, moment, override=False):
        return (r.hset if override else r.hsetnx)(self._key_value, label, moment.strftime(self.datetime_format))

    def _del_moment(self, r, label):
        return r.hdel(self._key_value, label)

    @staticmethod
    def _now():
        return datetime.datetime.now()

    def __str__(self):
        return '-'.join(list(self.args) + ['%s=%s' % (k, v) for k, v in self.kwargs.items()])

    def mark_failure(self):
        r = get_connection()
        now = self._now()
        self._del_moment(r, self.success_label)
        if self._set_moment(r, self.failure_label, now):
            _first_failure = now
            # reset all notifications
            for n in self._reference_monitor_notifications:
                self._del_moment(r, n._label)
        else:
            _first_failure = self._get_moment(r, self.failure_label)

        active_notifications = []
        for n in self._reference_monitor_notifications:
            if now >= _first_failure + n._timeout:
                _last_failure = self._get_moment(r, n._label)
                if _last_failure is None or ((n._repeat_timeout is not None) and (now > _last_failure + n._repeat_timeout)):
                    self._set_moment(r, n._label, now, override=True)
                    n._failure(self)

                active_notifications.append(n)

        return (now - _first_failure, active_notifications)

    def mark_success(self):
        r = get_connection()
        now = self._now()
        if not self._set_moment(r, self.success_label, now):
            return

        # reset all notifications
        for n in self._reference_monitor_notifications:
            if self._del_moment(r, n._label):
                # it there was notification, send about success
                if n._success is not None:
                    n._success(self)

    def cancel(self):
        r = get_connection()
        r.delete(self._key_value)

