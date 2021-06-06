from __future__ import annotations

import dataclasses

from django.db import models
from django.db.models.fields import Field
from django.utils.timezone import now as tz_now

from .models import FrozenObjectMeta
from .types import (
    AttributeList,
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


def split_list(values: AttributeList) -> AttributeList:
    """Extract just the top-level attributes."""
    return list(set([f.split("__")[0] for f in values if f]))


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
        local_fields = [f for f in local_fields if f.name in split_list(include)]

    if exclude:
        local_fields = [f for f in local_fields if f.name not in split_list(exclude)]

    if select_related:
        related_fields = [
            f for f in related_fields if f.name in split_list(select_related)
        ]
    else:
        related_fields = []

    return local_fields + related_fields


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

    def _next_level(values: AttributeList, field_name: str) -> AttributeList:
        prefix = f"{field_name}__"
        return list(set([f.split("__", 1)[1] for f in values if f.startswith(prefix)]))

    include = include or []
    exclude = exclude or []
    select_related = select_related or []
    select_properties = select_properties or []

    fields = gather_fields(obj.__class__, include, exclude, select_related)
    meta = FrozenObjectMeta(
        model=obj.__class__._meta.label,
        fields={f.name: klass_str(f) for f in fields},
        properties=select_properties,
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
                _next_level(include, f),
                _next_level(exclude, f),
                _next_level(select_related, f),
                _next_level(select_properties, f),
            )
            values[f] = dataclasses.asdict(frozen_obj)
        else:
            values[f] = val

    klass = meta.make_dataclass()
    return klass(meta, **values)


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