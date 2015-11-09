from surround.django import execution

from surround.django.logging import setupModuleLogger
setupModuleLogger(globals())



def execute_all(func, multi, max_parallel=None):
    return execution.MultiResult({name: execution.execute(func, parameters) for name, parameters in multi.items()})

