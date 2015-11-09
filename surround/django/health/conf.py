from django.conf import settings
from django.utils.module_loading import import_by_path

def setup(services):
    for name, class_path, kwargs in settings.SURROUND_HEALTH_SERVICES:
        health_class = import_by_path(class_path)
        services[name] = health_class(**kwargs)


services = dict()

setup(services)
