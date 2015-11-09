import os

def get_env_variable(name, default):
    try:
        return os.environ[name]
    except KeyError:
        return default

def get_bool_env_variable(name, default):
    value = get_env_variable(name, default)
    if value == 'True':
        return True
    if value == 'False':
        return False
    return default


def force_lazy_setting(entity):
    if isinstance(entity, str):
        return lazy_setting(entity)
    else:
        return entity


class LazyEvalWrapper(object):

    def __init__(self, func):
        self.func = func

    def __repr__(self):
        import inspect
        return 'lazy_eval(%r)' % self.func



class OnlyIfWrapper(object):

    def __init__(self, condition, value):
        self.condition = force_lazy_setting(condition)
        self.value = value


class LazySettingWrapper(object):

    def __init__(self, setting, **kwargs):
        self.setting = setting
        try:
            self.default = kwargs['default']
            self.has_default = True
        except KeyError:
            self.has_default = False

    def __repr__(self):
        return 'lazy_setting(%r)' % self.setting

class LazyFormatWrapper(object):

    def __init__(self, format, *args):
        self.format = format
        self.args = list(map(force_lazy_setting, args))

class LazySwitchWrapper(object):

    def __init__(self, condition, matches):
        self.condition = force_lazy_setting(condition)
        self.matches = matches

only_if = OnlyIfWrapper
lazy_setting = LazySettingWrapper
lazy_format = LazyFormatWrapper
lazy_switch = LazySwitchWrapper
lazy_eval = LazyEvalWrapper


class Resolver(object):

    def __init__(self, context):
        self.context = context

    def resolve(self, source):
        if isinstance(source, LazySwitchWrapper):
            condition = self.resolve(source.condition)
            match = source.matches[condition]
            return self.resolve(match)

        if isinstance(source, LazyEvalWrapper):
            return self.resolve(eval(source.func, self.context))

        if isinstance(source, LazySettingWrapper):
            if source.setting in self.context:
                value = self.context[source.setting]
            else:
                if source.has_default:
                    value = source.default
                else:
                    raise KeyError('%s not found in %s' % (source.setting, self.context))
            return self.resolve(value)


        if isinstance(source, LazyFormatWrapper):
            return source.format % tuple([self.resolve(arg) for arg in source.args])

        if isinstance(source, OnlyIfWrapper):
            if self.resolve(source.condition):
                return self.resolve(source.value)
            else:
                return None

        if isinstance(source, list):
            elements = []
            for element in source:
                value = self.resolve(element)
                if value is not None:
                    elements.append(value)
            return elements

        if isinstance(source, dict):
            elements = {}
            for k, v in source.items():
                key = self.resolve(k)
                if key is not None:
                    elements[key] = self.resolve(v)

            return elements


        if isinstance(source, tuple):
            elements = []
            for element in source:
                value = self.resolve(element)
                if value is not None:
                    elements.append(value)

            return tuple(elements)

        return source

    def resolve_in_place(self, source):
        resolved = self.resolve(source)
        if isinstance(source, dict):
            source.clear()
            source.update(resolved)
        else:
            raise Exception('cannot resolve in place')
