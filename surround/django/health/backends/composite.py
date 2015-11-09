from __future__ import absolute_import
from . import base

from surround.django.health.conf import services

class Check(base.Check):

    def __init__(self, names):
        self.children = [services[n] for n in names]

    def check(self):
        for c in self.children:
            c.check()


