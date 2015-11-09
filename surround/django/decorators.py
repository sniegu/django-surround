from django.conf import settings
from django.views.decorators.cache import cache_page as original_django_cache_page
from django.views.decorators.cache import never_cache
from django.utils.cache import add_never_cache_headers, patch_response_headers
from surround.django import platform_cache
from surround.django import utils
import functools

# IMPORTANT NOTE:
# in DEBUG mode django_cache_page decorator is an alias for never_cache, to ease developmenet process
if settings.DEBUG and not settings.SURROUND_CACHE_VIEWS:
    def django_cache_page(*args, **kwargs):
        return never_cache
else:
    django_cache_page = original_django_cache_page


def add_cache_headers(timeout):

    def wrapper(view):

        if (timeout is None) or (settings.DEBUG and not settings.SURROUND_CACHE_VIEWS):
            def wrapped(request, *args, **kwargs):
                response = view(request, *args, **kwargs)
                add_never_cache_headers(response)
                return response
        else:
            def wrapped(request, *args, **kwargs):
                response = view(request, *args, **kwargs)
                patch_response_headers(response, cache_timeout=timeout)
                return response

        if hasattr(view, '__name__'):
            wrapped = functools.wraps(view)(wrapped)

        return wrapped

    return wrapper

never_cache_headers = never_cache



def improved_cache_page(key, timeout=None, public_timeout=None, never_public=False):
    active_timeout = timeout
    if active_timeout is None:
        active_timeout = settings.DEFAULT_CACHE_TIME
    if (settings.DEBUG and not settings.SURROUND_CACHE_VIEWS):
        active_timeout = 0

    def wrapper(view):

        if never_public:
            headers_timeout = None
        else:
            if public_timeout is not None:
                headers_timeout = public_timeout
            else:
                headers_timeout = active_timeout

        return platform_cache.edge_side_cache(key=key, timeout=active_timeout)(add_cache_headers(timeout=headers_timeout)(view))

    return wrapper


def legacy_cache_page(key=None, timeout=None, public_timeout=None, never_public=False):
    return improved_cache_page(key=key, timeout=timeout, public_timeout=public_timeout, never_public=never_public)

