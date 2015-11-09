# coding=utf-8
from __future__ import absolute_import
from django.conf import settings
from django.shortcuts import render
from django.utils.module_loading import import_string

from surround.django.logging import setupModuleLogger
setupModuleLogger(globals())

process_esi = import_string(settings.SURROUND_ESI_IMPLEMENTATION_MODULE + '.process_esi')


def render_with_esi(request, *args, **kwargs):
    response = render(request, *args, **kwargs)

    if getattr(request, 'edge_side_include_used', False):
        process_esi(request, response)

    return response
