from django.conf import settings
from django.utils.module_loading import import_string

execute_all = import_string(settings.SURROUND_COROUTINE_IMPLEMENTATION_MODULE + '.execute_all')

