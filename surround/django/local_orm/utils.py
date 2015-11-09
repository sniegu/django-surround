from __future__ import absolute_import
from django.contrib.contenttypes.fields import GenericRelation, GenericForeignKey
from django.core.exceptions import ObjectDoesNotExist


class FilteredManagerMixin(object):

    def filter(self, **kwargs):
        return [obj for obj in self.all() if all([getattr(obj, k) == v for k, v in kwargs.items()])]

class DummyManager(FilteredManagerMixin):
    def __init__(self, owner, one_name):
        self.objects = list()
        self.owner = owner
        self.one_name = one_name

    def add(self, obj):
        if obj in self.objects:
            return
        if is_local_orm_model(obj):
            if getattr(obj, self.one_name) is not None:
                setattr(obj, self.one_name, None)

        self.objects.append(obj)
        if is_local_orm_model(obj):
            setattr(obj, self.one_name, self.owner)

    def remove(self, obj):
        if obj not in self.objects:
            return
        self.objects.remove(obj)
        if is_local_orm_model(obj):
            setattr(obj, self.one_name, None)

    def all(self):
        return self.objects

    def exists(self):
        return bool(self.objects)

    def get(self, **kwargs):
        for obj in self.objects:
            for k, v in kwargs.items():
                if getattr(obj, k) != v:
                    break
            else:
                return obj
        else:
            raise ObjectDoesNotExist()



class ManyToManyDummyManager(FilteredManagerMixin):

    def __init__(self, owner, through_one_name, through_to_name):
        self.objects = list()
        self.owner = owner
        self.through_one_name = through_one_name
        self.through_to_name = through_to_name

    def add(self, obj):
        if obj in self.objects:
            return
        self.objects.append(obj)
        if is_local_orm_model(obj):
            setattr(obj, self.through_one_name, self.owner)

    def remove(self, obj):
        if obj not in self.objects:
            return
        self.objects.remove(obj)
        if is_local_orm_model(obj):
            setattr(obj, self.through_one_name, None)

    def all(self):
        return [getattr(o, self.through_to_name) for o in self.objects]

    def exists(self):
        return bool(self.objects)



def is_local_orm_model(model):
    from .models import Model
    return isinstance(model, Model)




class Metadata(object):

    def __init__(self, django_model, **kwargs):
        self.django_model = django_model
        self.attrs = {}
        self.local_many_to_other_single = {}

        for k, v in kwargs.items():
            setattr(self, k, v)

    def copy_if_exists(self, model, name):
        if name in dir(model):
            self.attrs[name] = getattr(model, name).im_func

    def add_one_to_one_property(self, this_name, other_name):
        _this_name = '_' + this_name

        def one_to_one_getter(self):
            return getattr(self, _this_name)

        def one_to_one_setter(self, value):
            old_value = getattr(self, _this_name)
            if old_value == value:
                return

            setattr(self, _this_name, value)

            if is_local_orm_model(old_value):
                setattr(old_value, other_name, None)

            if is_local_orm_model(value):
                setattr(value, other_name, self)

        self.attrs[_this_name] = None
        self.attrs[this_name] = property(one_to_one_getter, one_to_one_setter)

    def add_foreign_key_property_one(self, one_name, many_name):
        _one_name = '_' + one_name
        if many_name is not None:
            many_name = many_name.rstrip('+')

        def foreign_one_getter(self):
            return getattr(self, _one_name)

        def foreign_one_setter(self, value):
            old_value = getattr(self, _one_name)
            if old_value == value:
                return
            setattr(self, _one_name, value)

            if is_local_orm_model(old_value):
                getattr(old_value, many_name if many_name is not None else old_value._meta.other_single_to_local_many[one_name]).remove(self)

            if is_local_orm_model(value):
                try:
                    getattr(value, many_name if many_name is not None else value._meta.other_single_to_local_many[one_name]).add(self)
                except KeyError:
                    from IPython import embed ; embed()

        self.attrs[_one_name] = None
        self.attrs[one_name] = property(foreign_one_getter, foreign_one_setter)

    def add_simple_field(self, field):
        from django.db.models.fields import NOT_PROVIDED
        default = (None if field.default == NOT_PROVIDED else field.default)
        self.attrs[field.name] = default
        if field.choices:
            choices_map = { k: v for k, v in field.choices }

            def get_display(instance):
                value = getattr(instance, field.name)
                return choices_map.get(value, value)

            self.attrs['get_%s_display' % field.name] = get_display

    def add_foreign_key_property_many(self, one_name, many_name):

        self.local_many_to_other_single[many_name] = one_name

        _many_name = '_' + many_name

        def foreign_many_getter(self):
            v = getattr(self, _many_name)
            if v is not None:
                return v
            v = DummyManager(self, one_name)
            setattr(self, _many_name, v)
            return v

        self.attrs[_many_name] = None
        self.attrs[many_name] = property(foreign_many_getter)

    def add_local_many_to_many_property(self, local_name, through_one_name, through_to_name):
        _local_name = '_' + local_name

        def local_many_to_many_getter(self):
            v = getattr(self, _local_name)
            if v is not None:
                return v
            v = ManyToManyDummyManager(self, through_one_name, through_to_name)
            setattr(self, _local_name, v)
            return v

        self.attrs[_local_name] = None
        self.attrs[local_name] = property(local_many_to_many_getter)

    def generate(self):
        if self.django_model is None:
            return

        from django.db.models.fields.related import ForeignKey, OneToOneField

        self.copy_if_exists(self.django_model, '__unicode__')
        self.copy_if_exists(self.django_model, '__str__')
        self.copy_if_exists(self.django_model, '__repr__')

        self.attrs.update({n: getattr(self.django_model, n) for n in filter(lambda n: (n == n.upper() and not n.startswith('_')), dir(self.django_model))})

        # TODO: change class generation - make a separate class base
        if 'CONFIG' in self.attrs:
            del self.attrs['CONFIG']

        for field in self.django_model._meta.local_many_to_many:
            if isinstance(field, GenericRelation):
                raise Exception('it should not happen')
            else:
                self.add_local_many_to_many_property(field.name, field.m2m_field_name(), field.m2m_reverse_field_name())


        for field in self.django_model._meta.fields:
            if isinstance(field, OneToOneField):
                self.add_one_to_one_property(field.name, field.related.get_accessor_name())
            elif isinstance(field, ForeignKey):
                self.add_foreign_key_property_one(field.name, field.related.get_accessor_name())
            else:
                self.add_simple_field(field)

        for field in self.django_model._meta.virtual_fields:
            if isinstance(field, GenericForeignKey):
                self.add_foreign_key_property_one(field.name, None)
            if isinstance(field, GenericRelation):
                assert field.content_type_field_name.endswith('_type')
                assert field.object_id_field_name.endswith('_id')
                one_name = field.content_type_field_name[:-5]
                assert field.object_id_field_name[:-3] == one_name
                self.add_foreign_key_property_many(one_name, field.name)

        for related in self.django_model._meta.get_all_related_objects():
            if isinstance(related.field, OneToOneField):
                self.add_one_to_one_property(related.get_accessor_name(), related.field.name)
            elif isinstance(related.field, ForeignKey):
                self.add_foreign_key_property_many(related.field.name, related.get_accessor_name())

        def init(self, **kwargs):

            for k, v in kwargs.items():
                setattr(self, k, v)

        self.attrs['__init__'] = init
        self.other_single_to_local_many = {v: k for k, v in self.local_many_to_other_single.items()}



class ObjectManager(object):

    def __init__(self):
        pass

    def _process_kwargs(self, kwargs):
        result = {}
        for k, v in kwargs.items():
            # this code is very dummy, but it is sufficient for the time being
            if k.endswith('__iexact'):
                k = k[:-8]
            result[k] = v
        return result


    def get_or_create(self, **kwargs):
        return self._model(**self._process_kwargs(kwargs)), True

    def get(self, **kwargs):
        return self._model(**self._process_kwargs(kwargs))


