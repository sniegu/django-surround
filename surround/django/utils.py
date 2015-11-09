# coding=utf-8
from __future__ import absolute_import

import functools
import re
from django.utils.functional import lazy
from django.core.urlresolvers import reverse
from django.conf import settings
from urlparse import urljoin
import datetime
from collections import namedtuple

from surround.django.logging import setupModuleLogger
setupModuleLogger(globals())


def add_ttl_header(response, timeout):
    response['X-TTL'] = str(timeout)

def add_forward_error_header(response):
    response['X-SURROUND-Forward-Error'] = '1'


def response_function_to_decorator(function):

    def _decorator(*fun_args, **fun_kwargs):

        def _bound_decorator(view_func):

            @functools.wraps(view_func)
            def _decorated(request, *args, **kwargs):
                response = view_func(request, *args, **kwargs)
                function(response, *fun_args, **fun_kwargs)
                return response

            return _decorated

        return _bound_decorator

    return _decorator

def identity_decorator(view):
    return view

def print_decorator(view):
    print('decorating: %s' % view)
    return view

FORCED_TTL_HEADER = 'X-SURROUND-FORCED-TTL'

def pass_forced_ttl_timeout(response, timeout):
    response[FORCED_TTL_HEADER] = timeout
    return response

def fetch_forced_ttl_timeout(response, default):
    if FORCED_TTL_HEADER in response:
        value = response[FORCED_TTL_HEADER]
        del response[FORCED_TTL_HEADER]
        return int(value)
    return default


def absolute_url(request, path, with_scheme=False):
    if with_scheme:
        scheme = 'https' if request.is_secure() else 'http'
        return urljoin('%s://%s/' % (scheme, request.get_host()), path)
    else:
        return urljoin('//%s/' % request.get_host(), path)


lazy_reverse = lazy(reverse, str)

def depoloniser(text):
    ltrPL = u'ąćęłńóśźżĄĆĘŁŃÓŚŹŻ'
    ltrnoPL = u'acelnoszzACELNOSZZ'
    ltrPL_pattern = u'%s' % '|'.join(ltrPL)

    def _sub(match_object):
        return ltrnoPL[ltrPL.find(match_object.group(0))]

    return re.sub(ltrPL_pattern, _sub, text)

class Timer:
    def __init__(self, text='took', logger=debug):
        self.text = text
        self.logger = logger

    def __enter__(self):
        self.start = datetime.datetime.now()
        return self

    def __exit__(self, *args):
        self.end = datetime.datetime.now()
        self.interval = self.end - self.start
        self.logger('%s: %s [%s - %s]' % (self.text, self.interval, self.start, self.end))


class CacheKey(object):

    ARGUMENT_PATTERN = re.compile('{([^}]+)}')

    def __init__(self, pattern):
        self.pattern = pattern
        self.arguments = [m.group(1) for m in CacheKey.ARGUMENT_PATTERN.finditer(self.pattern)]
        self.full_pattern = settings.INSTANCE_NAME + ':' + pattern

    def __call__(self, *args, **kwargs):
        for u, a in enumerate(args):
            kwargs[self.arguments[u]] = a
        return self.full_pattern.format(**kwargs)

    def __str__(self):
        return self.full_pattern

    def __repr__(self):
        return 'CacheKey(%r)' % self.pattern

    def __add__(self, other):
        return CacheKey(self.pattern + ':' + str(other))


class CacheProxy(object):
    def __init__(self, func, backend, timeout, key):
        self.func = func
        self.backend = backend
        self.timeout = timeout
        self.key = key
        #if key is not None else CacheKey(self.func.__name__ + ''.join([':{u}' for u in xrange(self.func.func_code.co_argcount)]))

    def _key(self, args, kwargs):
        return self.key(*args, **kwargs)

    def __call__(self, *args, **kwargs):
        key = self._key(args, kwargs)
        obj = self.backend.get(key)
        if obj is not None:
            return obj
        obj = self.func(*args, **kwargs)
        self.backend.set(key, obj, self.timeout)
        return obj

    def delete(self, *args, **kwargs):
        return self.backend.delete(self._key(args, kwargs))

    def purge(self, *args, **kwargs):
        return self.delete(*args, **kwargs)

    def force(self, *args, **kwargs):
        self.delete(*args, **kwargs)
        return self(*args, **kwargs)


def cache_result(timeout, key, cache='default'):
    from django.core.cache import get_cache
    backend = get_cache(cache)

    def decorator(func):
        return CacheProxy(func, backend, timeout, key)

    return decorator

def getattr_if_not_none(obj, name, default=None):
    if obj is not None:
        return getattr(obj, name, default)
    else:
        return default


def print_traceback(func):
    import functools

    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception:
            import traceback
            traceback.print_exc()
            raise

    return wrapped

if settings.SURROUND_RUNNING_ON_PLATFORM:
    def get_client_ip(request):
        try:
            return request.META['HTTP_X_FORWARDED_FOR']
        except KeyError:
            return request.META.get('REMOTE_ADDR', None)
else:
    def get_client_ip(request):
        return request.META.get('REMOTE_ADDR', None)


class ExtendedOrigin(namedtuple('ExtendedOrigin', ['ip', 'referer'])):
    __slots__ = ()

    # def __str__(self):
    #     return 's/%s/v/%s/t/%s/m/%s' % (self.collection_id, self.version, self.variant, self.module_id)

    @classmethod
    def from_request(cls, request):
        return cls(ip=get_client_ip(request), referer=request.META.get('HTTP_REFERER', None))

    @classmethod
    def empty(cls):
        return cls(ip='<empty>', referer='<empty>')


def get_arg_from_post_then_get(request, name, default=None):
    try:
        return request.POST[name]
    except KeyError:
        pass

    try:
        return request.GET[name]
    except KeyError:
        pass

    return default


class AttrDict(object):

    def __init__(self, internal=None):
        self.__dict__['_internal'] = internal if internal is not None else dict()

    def items(self):
        return self._internal.items()

    def values(self):
        return self._internal.values()

    def keys(self):
        return self._internal.keys()

    def __iter__(self):
        return self._internal.__iter__()

    def __getitem__(self, key):
        return self._internal.__getitem__(key)

    def __setitem__(self, key, value):
        return self._internal.__setitem__(key, value)

    def __getattr__(self, key):
        return self._internal.__getitem__(key)

    def __setattr__(self, key, value):
        return self._internal.__setitem__(key, value)

    def __dir__(self):
        return self._internal.__dir__()


def always_string(value):
    if isinstance(value, str):
        return value
    if isinstance(value, unicode):
        return value.encode('utf-8')
    return str(value)


def regex_domain(domain):
    return re.sub(r'\.', r'\.', domain)

def subdomain(sub):
    return r'^' + sub + r'\.' + regex_domain(settings.TOP_DOMAIN)
