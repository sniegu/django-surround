from __future__ import absolute_import

from django.conf import settings
import logging

def _module_logger_helper(glob):

    logger_path = '.'.join([settings.SURROUND_ROOT_LOGGER_NAME, glob['__name__']])
    logger = logging.getLogger(logger_path)

    entities = {}
    entities['logger'] = logger
    for level in ['debug', 'info', 'warning', 'error', 'critical']:
        entities[level] = getattr(logger, level)

    return entities

def prepare_module_logger(glob):

    return type('logging', (object,), _module_logger_helper(glob))

def setupModuleLogger(glob):
    glob.update(_module_logger_helper(glob))
