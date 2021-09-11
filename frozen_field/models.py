from __future__ import annotations

import dataclasses
from datetime import datetime
from importlib import import_module

from django.db.models.fields import Field
from django.utils.timezone import now as tz_now

from .types import (
    AttributeList,
    FrozenModel,
    IsoTimestamp,
    MetaFieldMap,
    ModelName,
    PickleReducer,
)


def _reduce(obj: FrozenModel) -> PickleReducer:
    """
    Return a tuple for use as the dataclass __reduce__ method.

    Dynamically-created dataclass don't pickle well as pickle can't find
    the class in the module (as it doesn't exist). To get around this we
    need to provide the dataclass with a `__reduce__` method that pickle
    can use.

    See https://docs.python.org/3/library/pickle.html#object.__reduce__

    Because the model doesn't exist we take the second option in the article
    above:

        > When a tuple is returned, it must be between two and six items long.
        > Optional items can either be omitted, or None can be provided as their
        > value. The semantics of each item are in order:
        >
        > A callable object that will be called to create the initial version of
        > the object.
        >
        > A tuple of arguments for the callable object. An empty tuple must be
        > given if the callable does not accept any argument.

    The return value is a 2-tuple that contains a function used to reproduce the
    object, and a 1-tuple containing the argument to be passed to the function,
    which in this case is the dict representation of the dataclass.

    """
    data = dataclasses.asdict(obj)
    # circ. import issue
    from .serializers import unfreeze_object

    return (unfreeze_object, (data,))


def strip_meta(value: dict) -> dict:
    """Strip the "_meta" node from dict, recursively."""
    result = {}
    for k, v in value.items():
        if k == "_meta":
            continue
        if isinstance(v, dict):
            result[k] = strip_meta(v)
        else:
            result[k] = v
    return result


@dataclasses.dataclass
class FrozenObjectMeta:
    """
    Dataclass for frozen object metadata, extracted from model._meta.

    This dataclass lies at the heart of the freezing process. By capturing the
    structure of a model (type, fields) it controls how the fields on a model
    object are serialized, and in reverse how JSON is deserialized (by
    determining the destination field of each serialized JSON value.)

    As an example, a Decimal field on a model would be serialized (using the
    DjangoJSONSerializer) as a string: `"cost": "1.49"`. When it comes to
    deserializing this value we need to know that it is a Decimal and not a
    string, which is where this meta model comes in. It serializes the structure
    of the model:

        {
            "model": "app.Model",
            "fields": {
                "cost": "django.db.models.fields.DecimalField"
            },
            "properties": ["full_name"],
            "frozen_at": "2021-06-04T18:10:30.549Z"
        }

    When the JSON is deserialized, we can look up the type of the field, and use
    that to convert the value back to a Decimal. In essence it does this:

        >>> cost = DecimalField.to_python("1.49")
        >>> cost
        Decimal('1.49')

    Building on this, this field information is used to create a dynamic dataclass
    that represents the model at the point of freezing.

    """

    model: ModelName
    fields: MetaFieldMap = dataclasses.field(default_factory=dict)
    properties: AttributeList = dataclasses.field(default_factory=list)
    frozen_at: datetime | IsoTimestamp = dataclasses.field(default_factory=tz_now)

    @property
    def cls_name(self) -> str:
        """Return a new class name for dataclass created from this meta object."""
        return f"Frozen{self.model.split('.')[-1]}"

    @property
    def frozen_attrs(self) -> AttributeList:
        """Return list of frozen attr names, inc. properties."""
        return sorted(list(set(list(self.fields.keys()) + self.properties)))

    def is_related_field(self, field_name: str) -> bool:
        """Return True if the field_name is a ForeignKey / OneToOneField."""
        if field_name in self.properties:
            return False
        _, klass = self.fields[field_name].rsplit(".", 1)
        return klass in ["ForeignKey", "OneToOneField"]

    def is_frozen(self, field_name: str) -> bool:
        """Return True if the fied_name is a FrozenObjectField."""
        if field_name in self.properties:
            return False
        _, klass = self.fields[field_name].rsplit(".", 1)
        return klass == "FrozenObjectField"

    def is_property(self, field_name: str) -> bool:
        """Return True if the fied_name is a property, not a field."""
        return field_name in self.properties

    def make_dataclass(self) -> type:
        """Create dynamic dataclass from the meta info."""
        klass = dataclasses.make_dataclass(
            cls_name=self.cls_name,
            fields=["_meta"] + self.frozen_attrs,
            frozen=True,
            namespace={
                # used to support pickling - see _reduce docstring
                "__reduce__": _reduce,
                # consider two objs equal if all properties match
                "__eq__": lambda obj1, obj2: vars(obj1) == vars(obj2),
                # 'clean' dict by removing "_meta" nodes - just the attrs
                "json_data": lambda obj: strip_meta(dataclasses.asdict(obj)),
            },
        )
        klass.__module__ = __name__
        return klass

    def _field(self, name: str) -> Field:
        """Return a Field object as represented by the field_name."""
        module, klass = self.fields[name].rsplit(".", 1)
        # force blank, null as we have to deal with whatever we are given
        return getattr(import_module(module), klass)(blank=True, null=True)

    def to_python(self, field_name: str, value: object) -> object | None:
        """Cast value using its underlying field.to_python method."""
        if field_name in self.properties:
            return value
        field = self._field(field_name)
        return field.to_python(value)
