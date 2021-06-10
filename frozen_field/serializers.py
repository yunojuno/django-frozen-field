from __future__ import annotations

import dataclasses
from collections import defaultdict

from django.db import models
from django.db.models.fields import Field
from django.utils.timezone import now as tz_now

from .exceptions import FrozenObjectError
from .models import FrozenObjectMeta
from .types import (
    AttributeList,
    AttributeMap,
    AttributeName,
    FieldConverterMap,
    FrozenModel,
    klass_str,
)


def strip_dict(values: FieldConverterMap, prefix: AttributeName) -> FieldConverterMap:
    """Strip dict in same way as strip_list does for lists."""
    return {
        k.removeprefix(f"{prefix}__"): v
        for k, v in values.items()
        if k.startswith(prefix) and k != prefix
    }


def gather_fields(
    klass: type[models.Model],
    include: AttributeList | None,
    exclude: AttributeList | None,
    select_related: AttributeList | None,
) -> list[Field]:
    """Return subset of obj fields that will be serialized."""
    local_fields = [f for f in klass._meta.local_fields if not f.related_model]
    related_fields = [f for f in klass._meta.local_fields if f.related_model]

    if include:
        _local = [f for f in local_fields if f.name in include]
        _related = [f for f in related_fields if f.name in include]
    # include and exclude are mutually exclusive
    elif exclude:
        _local = [f for f in local_fields if f.name not in exclude]
        _related = []
    # default option is all local fields, no related fields
    else:
        _local = local_fields
        _related = []

    if select_related:
        _related += [f for f in related_fields if f.name in select_related]

    return _local + _related


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

    _include = split_fields(include)
    _exclude = split_fields(exclude)
    _related = split_fields(select_related)
    _props = split_fields(select_properties)

    fields = gather_fields(
        obj.__class__,
        list(_include.keys()),
        list(_exclude.keys()),
        list(_related.keys()),
    )
    meta = FrozenObjectMeta(
        model=obj.__class__._meta.label,
        fields={f.name: klass_str(f) for f in fields},
        properties=list(_props.keys()),
        frozen_at=tz_now(),
    )

    values = {}
    for f in meta.frozen_attrs:
        val = getattr(obj, f)
        if isinstance(val, models.Model):
            # ok - we're going again, but before we do we need to strip
            # off the current field prefix from all values in the AttributeLists
            frozen_obj = freeze_object(
                val,
                _include.get(f),
                _exclude.get(f),
                _related.get(f),
                _props.get(f),
            )
            values[f] = frozen_obj
        elif dataclasses.is_dataclass(val):
            # we have a pre-frozen dataclass. if the user has specified
            # specific fields to be controlled in this object then we
            # fail hard - if the object is already frozen we have no
            # control over it.
            if any(
                [
                    _include.get(f),
                    _exclude.get(f),
                    _related.get(f),
                    _props.get(f),
                ]
            ):
                raise FrozenObjectError(
                    "Invalid FrozenObjectField settings - the field "
                    f"'{obj.__class__.__name__}.{f}' is already frozen. "
                    "You cannot control the serialization of frozen sub-fields."
                )
            values[f] = val
        else:
            values[f] = val

    klass = meta.make_dataclass()
    return klass(meta, **values)


def unfreeze_object(
    frozen_object: dict | None, field_converters: FieldConverterMap | None = None
) -> FrozenModel:
    """Deserialize a frozen object from stored JSON."""
    if not frozen_object:
        return None
    data = frozen_object.copy()
    meta = FrozenObjectMeta(**data.pop("_meta"))
    values: dict[str, object] = {}
    field_converters = field_converters or {}
    for k, v in data.items():
        # if we've stored None, return None - don't attempt to cast
        if v is None:
            values[k] = v
        # if we find another frozen object, recurse.
        if meta.is_related_field(k) or meta.is_frozen_field(k):
            converters = strip_dict(field_converters, k)
            values[k] = unfreeze_object(v, converters)
        elif k in field_converters:
            # if we find a specific override us that,
            values[k] = field_converters[k](v)
        else:
            # else fallback to the underlying field conversion
            values[k] = meta.to_python(k, v)
    dataklass = meta.make_dataclass()
    return dataklass(meta, **values)


def split_fields(fields: AttributeList | None) -> AttributeMap:
    """
    Split elements in a list into a dict.

    This function does the ORM style splitting. Given a field name
    such as "foo__bar", it will create a dict {"foo": ["bar"]} -
    essentially returning the list of child fields for each top-level
    field.

    """
    result: AttributeMap = defaultdict(list)
    if not fields:
        return {}
    for f in fields:
        split = (f"{f}").split("__", 1)
        if len(split) == 1 and split[0] not in result:
            result[split[0]] = []
        if len(split) == 2:
            result[split[0]].append(split[1])
    return dict(result)
