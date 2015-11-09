from surround.django import redis
import pickle
from django.conf import settings
from surround.django import utils
import requests

from surround.django.logging import setupModuleLogger
setupModuleLogger(globals())


def execute(key, timeout, view_func, request, args, kwargs):
    r = redis.get_connection()
    method_key = key + ':method:%s' % request.method.lower()
    hits_key = method_key + ':obj.hits'

    response = r.get(method_key)

    if response is not None:
        response = pickle.loads(response)
        hits = r.incr(hits_key)
        response['X-Cache'] = 'HIT %d' % hits
        return response
    # print('platform cache: %s' % k)

    response = view_func(request, *args, **kwargs)
    response['X-ESCache-Key-With-Method'] = method_key

    if response.status_code >= 400:
        timeout = settings.SURROUND_PLATFORM_CACHE_FAILED_TTL_TIMEOUT

    timeout = utils.fetch_forced_ttl_timeout(response, timeout)

    if settings.SURROUND_DEV_ENABLE_EDGE_SIDE_CACHE:
        if 'Vary' not in response:
            r.set(method_key, pickle.dumps(response))
            r.set(hits_key, 0)
            r.expire(method_key, timeout)
            r.expire(hits_key, timeout)
        response['X-Cache'] = 'MISS'
    else:
        response['X-Cache'] = 'DISABLED'
    return response


def purge(key_mask):
    redis.purge(key_mask + ':method:*')


def warm_cache(url):
    requests.head(url)

def purge_url(url):
    pass
    # for_each_server('BAN', url)



def internal_redirect(request, url, content_type=None, host_header=None):
    import proxy.views
    debug('internal django redirect %s -> %s (%s)', request.build_absolute_uri(), url, host_header)
    requests_args = dict(verify=False, allow_redirects=False)
    if host_header is not None:
        requests_args.update(headers={'Host': host_header})
    response = proxy.views.proxy_view(request, url, requests_args=requests_args)

    if content_type is not None:
        response['Content-Type'] = content_type

    del response['Set-Cookie']

    return response

