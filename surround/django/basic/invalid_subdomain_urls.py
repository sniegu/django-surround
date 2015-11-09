from django.conf.urls import patterns, url
from django.http import Http404

def invalid_host_view(request):
    raise Http404('unmatched domain: %s' % request.get_host())

urlpatterns = patterns('portal.views',
                       url(r'^.*$', invalid_host_view),
)
