from surround.django import utils

cache = utils.CacheKey('platform')
url_key = cache + 'url:{url}'
