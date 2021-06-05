from __future__ import annotations

import dataclasses
from datetime import datetime
from importlib import import_module

from django.db import models
from django.db.models.fields import Field
from django.utils.timezone import now as tz_now

from .types import (
    AttributeList,
    FieldConverterMap,
    FrozenModel,
    IsoTimestamp,
    MetaFields,
    ModelName,
    PickleReducer,
    klass_str,
)


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
    fields: MetaFields = dataclasses.field(default_factory=dict)
    properties: AttributeList = dataclasses.field(default_factory=list)
    frozen_at: datetime | IsoTimestamp = dataclasses.field(default_factory=tz_now)

    @property
    def cls_name(self) -> str:
        """Return a new class name for dataclass created from this meta object."""
        return f"Frozen{self.model.split('.')[-1]}"

    @property
    def frozen_attrs(self) -> AttributeList:
        """Return list of frozen attr names, inc. properties."""
        return list(self.fields.keys()) + self.properties

    @classmethod
    def has_meta(cls, value: object) -> bool:
        """Return True if value looks like it contains a meta dict."""
        if not value:
            return False

        if not isinstance(value, dict):
            return False

        return "meta" in value and "frozen_at" in value["meta"]

    def make_dataclass(self) -> type:
        """Create dynamic dataclass from the meta info."""
        klass = dataclasses.make_dataclass(
            cls_name=self.cls_name,
            fields=["meta"] + self.frozen_attrs,
            frozen=True,
            namespace={
                # used to support pickling - see _reduce docstring
                "__reduce__": _reduce,
                # consider two objs equal if all properties match
                "__eq__": lambda obj1, obj2: vars(obj1) == vars(obj2),
                "data": lambda obj: {
                    k: v for k, v in dataclasses.asdict(obj).items() if k != "meta"
                },
            },
        )
        klass.__module__ = __name__
        return klass

    def parse_obj(self, obj: models.Model) -> dict[str, object]:
        """Extract {attr: value} dict from a model instance using meta info."""
        if obj._meta.label != self.model:
            raise ValueError(
                f"Incorrect object type; expected {self.model}, got {obj._meta.label}."
            )
        values: dict[str, object] = {}
        for f in self.frozen_attrs:
            val = getattr(obj, f)
            if isinstance(val, models.Model):
                frozen_obj = freeze_object(val)
                values[f] = dataclasses.asdict(frozen_obj)
            else:
                values[f] = val
        return values

    def _field(self, name: str) -> Field:
        """Return a Field object as represented by the field_name."""
        module, klass = self.fields[name].rsplit(".", 1)
        # force blank, null as we have to deal with whatever we are given
        return getattr(import_module(module), klass)(blank=True, null=True)

    def to_python(self, field_name: str, value: object) -> object:
        """Cast value using its underlying field.to_python method."""
        if field_name in self.properties:
            return value
        field = self._field(field_name)
        return field.to_python(value)


def _gather_fields(
    klass: type[models.Model],
    include: AttributeList | None,
    exclude: AttributeList | None,
    select_related: AttributeList | None,
) -> list[Field]:
    """Return subset of obj fields that will be serialized."""
    local_fields = [f for f in klass._meta.local_fields if not f.related_model]
    related_fields = [f for f in klass._meta.local_fields if f.related_model]

    if include:
        local_fields = [f for f in local_fields if f.name in include]

    if exclude:
        local_fields = [f for f in local_fields if f.name not in exclude]

    if select_related:
        related_fields = [f for f in related_fields if f.name in select_related]
    else:
        related_fields = []

    return local_fields + related_fields


def create_meta(
    klass: type[models.Model],
    include: AttributeList | None = None,
    exclude: AttributeList | None = None,
    select_related: AttributeList | None = None,
    select_properties: AttributeList | None = None,
) -> FrozenObjectMeta:
    """
    Create a new meta object from a model instance.

    The rules around the field parsing is as follows:

    * By default, all non-related attrs are "included"
    * By details, all related attrs are "excluded"
    * "included" and "excluded" are mutually exclusive
    * "included" takes precedence - use to select a subset of fields
    * "excluded" is used to remove fields from the default set
    * "fields" contains all of the local fields on the model,
        regardless of whether they are included or excluded - this
        is the master list of properties at the point of freezing.
    * "select_related" contains any additional related fields that should be
        added to the "include" list. Empty by default.

    All of the above are parsed to produce two lists - "include" and "exclude" that
    contain all of the local_fields.

    """
    if not issubclass(klass, models.Model):
        raise ValueError("'obj' must be a Django model")

    if include and exclude:
        raise ValueError("'include' and 'exclude' are mutually exclusive.")

    fields = _gather_fields(klass, include, exclude, select_related)

    return FrozenObjectMeta(
        model=klass._meta.label,
        fields={f.name: klass_str(f) for f in fields},
        properties=(select_properties or []),
        frozen_at=tz_now(),
    )


def freeze_object(
    obj: models.Model,
    include: AttributeList | None = None,
    exclude: AttributeList | None = None,
    select_related: AttributeList | None = None,
    select_properties: AttributeList | None = None,
) -> FrozenModel | None:
    """
    Create a new dataclass containing meta info and object properties.

    The process for freezing a Model instance is to first create the meta object
    that defines which fields we want to freeze, using that to create a new dynamic
    dataclass, and then creating an instance of the dataclass. It is this intermediate
    object that is serialized.

    """
    if obj is None:
        return obj

    meta = create_meta(
        obj.__class__,
        include=include,
        exclude=exclude,
        select_related=select_related,
        select_properties=select_properties,
    )
    dataklass = meta.make_dataclass()
    values = meta.parse_obj(obj)
    return dataklass(meta, **values)


def unfreeze_object(
    frozen_object: dict, field_converters: FieldConverterMap | None = None
) -> FrozenModel:
    """Deserialize a frozen object from stored JSON."""
    meta = FrozenObjectMeta(**frozen_object.pop("meta"))
    values: dict[str, object] = {}
    field_converters = field_converters or {}
    for k, v in frozen_object.items():
        # if we find another frozen object, recurse
        if FrozenObjectMeta.has_meta(v):
            values[k] = unfreeze_object(v)
        elif k in field_converters:
            # if we find a specific override us that,
            values[k] = field_converters[k](v)
        else:
            # else fallback to the underlying field conversion
            values[k] = meta.to_python(k, v)
    dataklass = meta.make_dataclass()
    return dataklass(meta, **values)


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
    return (unfreeze_object, (data,))
