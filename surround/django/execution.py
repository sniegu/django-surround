from __future__ import absolute_import
from collections import namedtuple
from django.conf import settings

from surround.django.logging import setupModuleLogger

setupModuleLogger(globals())

class Result(namedtuple('Result', ['value', 'exception'])):

    __slots__ = ()

    def return_result(self):
        self.throw_if_exception()

        return self.value

    def return_result_or_none(self):
        if not self.success:
            return None

        return self.value

    def throw_if_exception(self):

        if self.exception is not None:
            raise self.exception

    @property
    def success(self):
        return self.exception is None

    def map_state(self, on_success, *exception_clauses):
        if self.success:
            return on_success
        for exceptions, result in exception_clauses:
            if isinstance(self.exception, exceptions):
                return result
        self.throw_if_exception()



class Parameters(namedtuple('Parameters', ['args', 'kwargs'])):

    __slots__ = ()

    def __str__(self):
        return ', '.join(list(map(str, self.args)) + ['%s=%r' % (k, v) for k, v in self.kwargs.items()])


def parameters(*args, **kwargs):
    return Parameters(args, kwargs)


def execute(func, parameters):
    try:
        return Result(func(*parameters.args, **parameters.kwargs), None)
    except Exception as e:
        # logger.exception('during execution of %s(%s) exception occurred: %s', func, parameters, e)
        if settings.SURROUND_EXECUTION_DEBUG:
            raise
        return Result(None, e)

class ExecutionException(Exception):
    pass

class MultiParameters(dict):


    def bind(self, name, *args, **kwargs):
        self[name] = Parameters(args, kwargs)

    def add(self, name, parameters):
        self[name] = parameters


class MultiResult(object):

    def __init__(self, results):
        self.results = results

    def __getitem__(self, key):
        try:
            return self.results[key].return_result()
        except KeyError as e:
            raise ExecutionException('failed to find key "%s" in %s: %s' % (key, self, e))

    def get_result(self, key, throw_if_exception=True):
        result = self.results[key]
        if throw_if_exception:
            result.throw_if_exception()
        return result

    def items(self):
        return self.results.items()

    def keys(self):
        return self.results.keys()


class LazyFactory(object):

    def __init__(self, class_owner, multi_func_name, const_attributes={}):
        self.class_owner = class_owner
        self.multi_func_name = multi_func_name
        self.const_attributes = const_attributes

    @property
    def multi_func(self):
        return getattr(self.class_owner, self.multi_func_name)

    def __str__(self):
        return '%s.%s.%s' % (self.class_owner.__module__, self.class_owner.__name__, self.multi_func_name)

    def __call__(self, *args, **kwargs):
        return LazyObject(self, Parameters(args, kwargs), self.const_attributes)


class LazyObject(object):

    def __init__(self, factory, parameters, const_attributes):
        self._factory = factory
        self._parameters = parameters
        self._execution_result = None
        self._const_attributes = const_attributes

        for k, v in parameters.kwargs.items():
            setattr(self, k, v)

        for k, v in const_attributes.items():
            setattr(self, k, v)


    @property
    def _filled(self):
        return self._execution_result is not None

    def _fill(self, value):
        self._execution_result = value

    @property
    def _auto_filled(self):
        if not self._filled:
            # import traceback ; traceback.print_stack()
            self._fill(self._factory.multi_func.single(self._parameters))
        return self._execution_result.return_result()

    @property
    def _filled_value(self):
        return self._execution_result.return_result()

    @property
    def _success(self):
        return self._execution_result.success


    def __getattr__(self, name):
        return getattr(self._auto_filled, name)


    def __str__(self):
        return 'LazyObject(%s, %s, %s)' % (self._factory, self._parameters, 'filled' if self._filled else 'empty')

    __repr__ = __str__

    def __reduce__(self):
        return (self.__class__, (self._factory, self._parameters, self._const_attributes))

    def __dir__(self):
        return dir(self._auto_filled)


def multi_lazy_resolve(lazy_objects, final_throw_if_any=True, accumulate_successes=False):

    multi_parameters = MultiParameters()
    multi_func = None

    not_filled = []
    not_filled_number = 0
    if accumulate_successes:
        successes = []
    else:
        successes = None

    for lazy in lazy_objects:
        if lazy._filled:
            if accumulate_successes:
                successes.append(lazy._filled_value)
            continue

        not_filled.append(lazy)
        multi_parameters.add(not_filled_number, lazy._parameters)
        not_filled_number += 1

        next_multi_func = lazy._factory.multi_func
        if multi_func is None:
            multi_func = next_multi_func
        else:
            if multi_func != next_multi_func:
                raise ExecutionException('inconsistent multi functions stored in lazy objects')

    if multi_func is None:
        return successes

    multi_results = multi_func.multi(multi_parameters)

    for num, lazy in enumerate(not_filled):
        result = multi_results.get_result(num, throw_if_exception=False)
        lazy._fill(result)

        if result.success:
            if accumulate_successes:
                successes.append(lazy._filled_value)
        else:
            if final_throw_if_any:
                result.throw_if_exception()

    return successes


