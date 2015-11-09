from functools import wraps
from contextlib import contextmanager
from threading import local

thread_local = local()

from surround.django.logging import setupModuleLogger
setupModuleLogger(globals())

class LocalCacheBackend(object):
    def __init__(self):
        self.backend = {}

    def get(self, key):
        return self.backend.get(key, None)

    def set(self, key, value):
        self.backend[key] = value


def cached(func):
    name = func.__module__ + '.' + func.__name__

    def _get_key(args, kwargs):
        return name + ':a:' + ','.join(map(str, args)) + ':kw:' + ','.join(['%s=%s' % (k, v) for k, v in kwargs.items()])

    @wraps(func)
    def wrapped(*args, **kwargs):
        current = get_active()
        if current is None:
            return func(*args, **kwargs)

        key = _get_key(args, kwargs)

        cached_value = current.get(key)
        if cached_value is not None:
            return cached_value

        result = func(*args, **kwargs)
        current.set(key, result)
        return result

    def _force(value, args=[], kwargs={}):
        key = _get_key(args, kwargs)
        current = get_active()
        if current is None:
            raise Exception('forcing context cache value outside context')

        current.set(key, value)

    wrapped._force = _force
    wrapped._get_key = _get_key

    return wrapped


@contextmanager
def make_active(current):
    old = getattr(thread_local, 'backend', None)
    thread_local.backend = current
    try:
        yield current
    finally:
        if old is not None:
            thread_local.backend = old
        else:
            del thread_local.backend


def wrap_with_current(func):

    current = get_active()

    @wraps(func)
    def wrapped(*args, **kwargs):
        with make_active(current):
            return func(*args, **kwargs)

    return wrapped


def wrap_with_activate(func):

    @wraps(func)
    def wrapped(*args, **kwargs):
        with activate():
            return func(*args, **kwargs)

    return wrapped


def wrap_with_assure_active(func):

    @wraps(func)
    def wrapped(*args, **kwargs):
        with assure_active():
            return func(*args, **kwargs)

    return wrapped


def activate():
    return make_active(LocalCacheBackend())

@contextmanager
def assure_active():
    current = get_active()
    if current is not None:
        yield
    else:
        with activate():
            yield

def deactivate():
    return make_active(None)

def get_active():
    return getattr(thread_local, 'backend', None)

