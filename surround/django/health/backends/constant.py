from __future__ import absolute_import
from . import base

from surround.django.health.conf import services

class Check(base.Check):

    def __init__(self, value=True):
        self.value = value

    def check(self):

        if not self.value:
            raise Exception("constant check is set to False")


