from __future__ import absolute_import

from django_hosts.reverse import reverse_host
from django.conf import settings
from surround.django import redis
from surround.django import utils
from surround.django.utils import fetch_forced_ttl_timeout
from surround.django.utils import pass_forced_ttl_timeout
import functools
from . import keys
from django.utils.module_loading import import_string

from surround.django.logging import setupModuleLogger
setupModuleLogger(globals())

def make_key(host, path):
    return '%s:%s' % (host, path)


time_to_leave = utils.response_function_to_decorator(utils.add_ttl_header)

execute = import_string(settings.SURROUND_HTTPCACHE_IMPLEMENTATION_MODULE + '.execute')
purge = import_string(settings.SURROUND_HTTPCACHE_IMPLEMENTATION_MODULE + '.purge')
warm_cache = import_string(settings.SURROUND_HTTPCACHE_IMPLEMENTATION_MODULE + '.warm_cache')
internal_redirect = import_string(settings.SURROUND_HTTPCACHE_IMPLEMENTATION_MODULE + '.internal_redirect')
purge_url = import_string(settings.SURROUND_HTTPCACHE_IMPLEMENTATION_MODULE + '.purge_url')


purge_platform = purge


class EdgeSideCache(object):
    def __init__(self, key, timeout, view_func):
        functools.wraps(view_func)(self)
        self.cache_key = key
        self.timeout = timeout
        self.view_func = view_func

    def __call__(self, request, *args, **kwargs):
        # print('%s for %s, %s -> %s, %s' % (view_func.__name__, args, kwargs, a, key))
        # a = args + tuple(kwargs.values())
        if self.cache_key is None:
            k = keys.url_key(url=request.build_absolute_uri())
        else:
            k = self.cache_key(*args, **kwargs)
        # info('edge side cache args = %s, kwargs = %s, key = %s, timeout: %s', args, kwargs, k, timeout)

        return execute(k, self.timeout, self.view_func, request, args, kwargs)

    def purge(self, *args, **kwargs):
        if self.cache_key is None:
            # purging edge side cache with no cache key assigned is disabled
            return
        k = self.cache_key(*args, **kwargs)
        debug('purging edge side cache with key: %s', k)
        purge(k)

    def __repr__(self):
        return 'EdgeSideCache(%s.%s, %s, %r)' % (self.view_func.__module__, self.view_func.__name__, self.timeout, self.cache_key)


def edge_side_cache(key, timeout):

    def _decorator(view_func):

        return EdgeSideCache(key, timeout, view_func)

    return _decorator




