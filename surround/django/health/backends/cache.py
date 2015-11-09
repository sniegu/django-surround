from __future__ import absolute_import
from django.core.cache import get_cache
from . import base

class Check(base.Check):

    def __init__(self, cache_name):
        self.cache_name = cache_name

    def check(self):
        cache = get_cache(self.cache_name)

        cache.set('surround', 'itworks', 10)
        if cache.get("surround") != "itworks":
            raise Exception("Cache key does not match")


