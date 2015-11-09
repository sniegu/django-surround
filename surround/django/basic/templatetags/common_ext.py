# -*- coding: utf-8 -*-

from surround.django.utils import absolute_url, depoloniser
from django import template
from portal import hosts
from django_hosts.reverse import reverse_full
from django.core.urlresolvers import reverse
from django.conf import settings
import json

register = template.Library()


@register.simple_tag(takes_context=True)
def absolute_path(context, path):
    request = context['request']
    return absolute_url(request, path)


@register.simple_tag(takes_context=True)
def url_absolute(context, view, *args):
    request = context['request']
    return absolute_url(request, reverse(view, args=args))


@register.simple_tag(takes_context=True)
def url_absolute_with_scheme(context, view):
    request = context['request']
    return absolute_url(request, reverse(view), with_scheme=True)


@register.simple_tag
def static_get_absolute_url(model_or_instance, *args):
    return model_or_instance.static_get_absolute_url(*args)


@register.filter
def make_css_class(value):
    return depoloniser(value).replace(' ', '_').lower()

@register.filter
def setting_is_true(name):
    return getattr(settings, name)

@register.filter
def jsondumps(json_obj):
    return json.dumps(json_obj)


@register.filter
def make_schemeless(value):
    if value is None:
        return None
    if value.startswith('http:'):
        return value[5:]
    if value.startswith('https:'):
        return value[6:]
    return value



@register.simple_tag
def host_url(host, view, *args, **kwargs):
    return reverse_full(host, view, view_args=args, view_kwargs=kwargs)



ESI_LINK_TEMPLATE = '<esi:include src="%s" />'


@register.simple_tag(takes_context=True)
def esi_link(context, source):
    if source.startswith('//'):
        source = 'http:' + source
    context['request'].edge_side_include_used = True
    return ESI_LINK_TEMPLATE % source


@register.simple_tag(takes_context=True)
def esi_url(context, host, view, *args, **kwargs):
    url = reverse_full(host, view, view_args=args, view_kwargs=kwargs)
    return esi_link(context, url)
