from __future__ import annotations

import dataclasses
from importlib import import_module

from django.db import models
from django.db.models.fields import Field
from django.utils.timezone import now as tz_now

from .types import AttributeList, AttributeName, IsoTimestamp, ModelKlass, ModelName


@dataclasses.dataclass
class FrozenObjectMeta:
    """
    Dataclass for frozen object metadata, extracted from model._meta.

    This dataclass lies at the heart of the freezing process. By capturing the
    structure of a model (type, fields) it controls how the fields on a model
    object are serialized, and in reverse how JSON is deserialized (by
    determining the destination field of each serialized JSON value.)

    As an example, a Decimal field on a model would be serialized (using the
    DjanoJSONSerializer) as a string: `"cost": "1.49"`. When it comes to
    deserializing this value we need to know that it is a Decimal and not a
    string, which is where this meta model comes in. It serializes the structure
    of the model:

        {
            "model": "core.Address",
            "fields": {
                "cost": "django.db.models.fields.DecimalField"
            }
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
    fields: dict[AttributeName, ModelKlass]
    include: list[AttributeName]
    exclude: list[AttributeName]
    frozen_at: IsoTimestamp

    @property
    def cls_name(self) -> str:
        """Return a new class name for dataclass created from this meta object."""
        return f"Frozen{self.model.split('.')[-1]}"

    def get_dataclass(self) -> type:
        """Create dynamic dataclass from the meta info."""
        return dataclasses.make_dataclass(
            cls_name=self.cls_name,
            fields=["meta"] + self.include,
            frozen=True,
        )

    def get_dataclass_instance(self, **values: object) -> object:
        """Create dynamic dataclass instance from the meta info and values."""
        return self.get_dataclass()(self, **values)

    def extract_model_values(self, obj: models.Model) -> dict[str, object]:
        """Extract {name: value} dict from a model instance using meta info."""
        if obj._meta.label != self.model:
            raise ValueError(
                f"Incorrect object type; expected {self.model}, got {obj._meta.label}."
            )
        values: dict[str, object] = {}
        for f in self.include:
            val = getattr(obj, f)
            if isinstance(val, models.Model):
                frozen_obj = freeze_object(val)
                values[f] = dataclasses.asdict(frozen_obj)
            else:
                values[f] = val
        return values

    def _field(self, name: str) -> Field:
        """Return the Field class represented by the name."""
        module, klass = self.fields[name].rsplit(".", 1)
        return getattr(import_module(module), klass)

    def cast_field(self, field_name: str, value: object) -> object:
        """Cast value using its underlying field.to_python method."""
        field = self._field(field_name)
        return field().to_python(value)


def create_meta(
    obj: models.Model,
    include: AttributeList | None = None,
    exclude: AttributeList | None = None,
    select_related: AttributeList | None = None,
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
    if not isinstance(obj, models.Model):
        raise ValueError("'obj' must be a Django model")

    def fq(field: Field) -> str:
        return f"{field.__class__.__module__}.{field.__class__.__qualname__}"

    def copy_attr_list(attr_list: AttributeList | None) -> AttributeList:
        if attr_list:
            return attr_list.copy()
        return []

    _include = copy_attr_list(include) + copy_attr_list(select_related)
    _exclude = copy_attr_list(exclude)

    if _include and _exclude:
        raise ValueError("'include' and 'exclude' are mutually exclusive.")

    # the complete list of fields, included or not
    _all = obj._meta.local_fields

    # include all fields that are neither related nor in exclude
    if not _include:
        _include = [
            f.name for f in _all if f.name not in _exclude and not f.related_model
        ]

    # exclude all related fields and those not in _include
    if not _exclude:
        _exclude = [f.name for f in _all if f.name not in _include]

    return FrozenObjectMeta(
        model=obj._meta.label,
        fields={f.name: fq(f) for f in _all},
        include=_include,
        exclude=_exclude,
        frozen_at=tz_now(),
    )


def freeze_object(
    obj: models.Model,
    include: AttributeList | None = None,
    exclude: AttributeList | None = None,
    select_related: AttributeList | None = None,
) -> object:
    """Create dynamic dataclass mapping object properties."""
    meta = create_meta(
        obj,
        include=include,
        exclude=exclude,
        select_related=select_related,
    )
    values = meta.extract_model_values(obj)
    return meta.get_dataclass_instance(**values)


def unfreeze_object(frozen_object: dict) -> object:
    """Deserialize a frozen object from stored JSON."""
    if isinstance(frozen_object, str):  # type: ignore [unreachable]
        # include this "unreachable" condition as str <> dict is a really
        # common gotcha - json.dumps/loads confusion.
        raise ValueError("'frozen_object' is a str - please use json.loads")

    meta = FrozenObjectMeta(**frozen_object["meta"])
    values: dict[str, object] = {}
    for k, v in frozen_object.items():
        if k == "meta":
            continue
        # if we find another frozen object, recurse
        elif isinstance(v, dict) and "meta" in v:
            values[k] = unfreeze_object(v)
        else:
            values[k] = meta.cast_field(k, v)
    return meta.get_dataclass_instance(**values)
