from __future__ import absolute_import

from .utils import ObjectManager, Metadata

class ModelMetaclass(type):

    def __new__(cls, name, bases, attrs):

        meta_dict = {}

        for meta_name, meta_default in [('django_model', None), ('key_attributes', ())]:
            try:
                meta_dict[meta_name] = getattr(attrs['Meta'], meta_name)
            except (KeyError, AttributeError):
                meta_dict[meta_name] = meta_default

        _meta = Metadata(**meta_dict)
        _meta.generate()
        for k, v in _meta.attrs.items():
            if k not in attrs:
                attrs[k] = v

        # generated = generate_attributes(_meta.django_model)
        # _meta.generated = type('generated', (object,), generated)


        attrs['_meta'] = _meta
        attrs['objects'] = ObjectManager()

        return type.__new__(cls, name, bases, attrs)

    def __init__(cls, name, bases, attrs):
        super(ModelMetaclass, cls).__init__(name, bases, attrs)
        cls.objects._model = cls


class Model(object):

    __metaclass__ = ModelMetaclass

    def save(self, *args, **kwargs):
        pass
