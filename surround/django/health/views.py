from __future__ import absolute_import

from django.http import HttpResponse
from .conf import services

def check(request, service):
    try:
        service = services[service]
    except KeyError:
        return HttpResponse(status=404, content='DOES NOT EXIST')

    try:
        service.check()
        return HttpResponse(status=200, content='OK')

    except Exception as e:
        return HttpResponse(status=503, content="FAIL %s('%s')" % (e.__class__, e.message))





