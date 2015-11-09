import functools


def action(method, short_description=None, args=[], kwargs={}):

    @functools.wraps(method)
    def wrapped(modeladmin, request, queryset):
        for obj in queryset:
            method(obj, *args, **kwargs)

    if short_description is None:
        short_description = method.__name__

    return wrapped

def resolve_attribute(obj, attribute_name):
    value_or_method = getattr(obj, attribute_name)
    try:
        return value_or_method()
    except TypeError:
        return value_or_method


def absolute_link(label, address_attribute='get_absolute_url'):

    def absolute_link(model_object):
        return '<a href="%s">%s</a>' % (resolve_attribute(model_object, address_attribute), label)

    absolute_link.allow_tags = True
    absolute_link.__name__ = label
    return absolute_link
