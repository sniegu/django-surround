from __future__ import absolute_import

import functools
from . import headers
from django.http import HttpResponse
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.conf import settings
from django.utils.cache import patch_vary_headers
import copy


def cors_headers(profile=None, **kwargs):

    try:
        original_profile_config = settings.SURROUND_SIMPLE_CORS_PROFILES[profile]
    except KeyError:
        raise ImproperlyConfigured('unknown cors_headers profile: %s', profile)

    profile_config = copy.deepcopy(original_profile_config)
    profile_config.update(kwargs)

    allow_all = profile_config.get('allow_all', False)

    if not allow_all:
        allowed_domains = []
        for domain in profile_config.get('domains', settings.SURROUND_SIMPLE_CORS_COMMON_DOMAINS):
            allowed_domains += ['http://' + domain, 'https://' + domain]

    allow_credentials = profile_config.get('allow_credentials', False)
    allow_methods = profile_config.get('allow_methods', settings.SURROUND_SIMPLE_CORS_COMMON_ALLOWED_METHODS)
    allow_headers = [ "origin", "content-type", "accept", "x-requested-with" ]
    if allow_credentials:
        allow_headers += [ "authorization" ]


    allow_methods_string = ', '.join(allow_methods)
    allow_headers_string = ', '.join(allow_headers)


    def wrapper(func):

        @functools.wraps(func)
        def wrapped(request, *args, **kwargs):

            origin = request.META.get('HTTP_ORIGIN')

            if origin:
                if not allow_all:
                    if origin not in allowed_domains:
                        raise PermissionDenied()

            if (request.method == 'OPTIONS'):
                response = HttpResponse()
                response[headers.CONTENT_TYPE] = "text/plain"
            else:
                response = func(request, *args, **kwargs)

            patch_headers = False
            if allow_all:
                response[headers.ACCESS_CONTROL_ALLOW_ORIGIN] = "*"
                patch_headers = True
            else:
                if origin:
                    response[headers.ACCESS_CONTROL_ALLOW_ORIGIN] = origin
                    patch_headers = True

                patch_vary_headers(response, ['Origin'])

            if patch_headers:
                response[headers.ACCESS_CONTROL_ALLOW_HEADERS] = allow_headers_string
                response[headers.ACCESS_CONTROL_ALLOW_METHODS] = allow_methods_string
                response[headers.ACCESS_CONTROL_MAX_AGE] = "86400"

                if allow_credentials:
                    response[headers.ACCESS_CONTROL_ALLOW_CREDENTIALS] = 'true'

            return response

        return wrapped

    return wrapper



