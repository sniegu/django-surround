# coding=utf-8
from __future__ import absolute_import

from django.shortcuts import render
from surround.django import utils
from django.core.urlresolvers import reverse
from django.views.generic import View

class DeprecatedAddress(View):

    new_view_name = 'main_index'
    fixed_kwargs = {}

    def get(self, request, *args, **kwargs):
        kwargs.update(self.fixed_kwargs)

        response = render(request, 'deprecated_error_page.html', { 'url': reverse(self.new_view_name, args=args, kwargs=kwargs) }, status=404)
        utils.add_forward_error_header(response)
        return response
