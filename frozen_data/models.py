from __future__ import annotations

import json
from importlib import import_module
from typing import NoReturn

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.fields import Field
from django.db.models.fields.json import JSONField
from django.db.models.fields.related import RelatedField
from django.utils.timezone import now as tz_now

from frozen_data.exceptions import ExcludedAttribute, FrozenAttribute, StaleObjectError


def validate_raw(value: dict) -> None:
    """Validate the raw contents."""
    if "meta" not in value:
        raise ValidationError("Missing meta key.")

    if "model" not in value["meta"]:
        raise ValidationError("Missing meta.model key.")

    if not value["meta"]["model"]:
        raise ValidationError("Empty meta.model key.")

    if "fields" not in value["meta"]:
        raise ValidationError("Missing meta.fields key.")

    if "exclude" not in value["meta"]:
        raise ValidationError("Missing meta.exclude key.")


class FrozenObject:
    """
    Container for an object that looks like a frozen model.

    This class id designed to manage the deserialization (unfreezing)
    of data in the following form:

        {
            "meta": {
                "model": "core.Address",
                "frozen_at": "2021-05-28T16:42:43.829687+00:00",
                "fields": {
                    "id": ("django.db.models", "IntegerField"),
                    "line_1": ("django.db.models", ""CharField"),
                    "user": ("frozen_data.models", "FrozenObject")
                }
            },
            "id": 1,
            "line_1": "29 Acacia Avenue",
            "user": {
                "meta": {
                    "label": "auth.User",
                    "frozen_at": "...",
                    "fields": {
                        "id": "django.db.models.IntegerField",
                        "first_name": "django.db.models.CharField",
                        "last_name": "django.db.models.CharField"
                    }
                },
                "id": 1,
                "first_name": "Eric",
                "last_name": "Bananaman"
            }
        }

    When deserialized this object will support:

        >>> fo = FrozenObject({...})
        >>> fo.line_1
        '29 Acacia Avenue'
        >>> fo.user.first_name
        'Eric'

    """

    def validate_raw(self, value: dict) -> None:
        """Validate the raw contents."""
        if "meta" not in value:
            raise ValidationError("Missing meta key.")

        if "model" not in value["meta"]:
            raise ValidationError("Missing meta.model key.")

        if "fields" not in value["meta"]:
            raise ValidationError("Missing meta.fields key.")

        if "exclude" not in value["meta"]:
            raise ValidationError("Missing meta.exclude key.")

    def __init__(self, frozen_data: dict) -> None:
        self.raw = frozen_data

    def __str__(self) -> str:
        return f"FrozenObject[{self.model}]"

    def __setattr__(self, name: str, value: object) -> None:
        """Prevent setting of frozen attributes."""
        # this is the first propert set, so must pass through
        if name == "raw":
            # if we are deeply nested, this may be a str, not a dict
            if isinstance(value, str):
                value = json.loads(value)
            if isinstance(value, dict):
                self.validate_raw(value)
                super().__setattr__(name, value)
                return
            raise ValueError("raw must be a dict, or parseable str.")
        # # allow other arbitrary fields through if not in the frozen set
        # if name not in self.fields:
        #     return super().__setattr__(name, value)
        # prevent frozen attributes from being set
        raise FrozenAttribute

    def __getattr__(self, name: str) -> object:
        """
        Extract value from raw data.

        This method is only called if the attr requested is not found
        via the usual routes - i.e. on the object already.

        For non-related fields this uses the stored field type to
        convert the JSON value back to its python equivalent.

        For related fields, which are all serialized as "FrozenObject"
        fields, we return a nested FrozenObject instance. Turtles all
        the way down.

        """
        if name in self.exclude:
            raise ExcludedAttribute

        if name not in self.fields:
            raise AttributeError(f"{self} has no attribute '{name}'")

        field_klass = self.get_field_class(name)
        value = self.raw[name]

        # print(f"getting value {value} for field {field_klass}")
        from .fields import FrozenObjectField

        if issubclass(field_klass, FrozenObjectField):
            # found nested FrozenObject
            return FrozenObject(value)
        if issubclass(field_klass, (models.ForeignKey, models.OneToOneField)):
            # found nested FK
            return FrozenObject(value)
        if issubclass(field_klass, JSONField) and isinstance(value, str):
            value = json.loads(value)
        return field_klass().to_python(value)

    @property
    def model(self) -> str:
        """Return name of the model that is being frozen."""
        return self.raw["meta"]["model"]

    @property
    def fields(self) -> dict[str, tuple[str, str]]:
        return self.raw["meta"]["fields"]

    @property
    def exclude(self) -> list[str]:
        """List of field names to exclude in serialization."""
        return self.raw["meta"]["exclude"]

    def save(self, *args: object, **kwargs: object) -> NoReturn:
        raise StaleObjectError

    def get_field_class(self, name: str) -> Field:
        """Return the field represented by the name."""
        module, klass = self.fields[name]
        return getattr(import_module(module), klass)

    @classmethod
    def from_object(  # noqa: C901
        cls,
        instance: models.Model,
        deep_freeze: bool = False,
        exclude: list[str] | None = None,
    ) -> FrozenObject | None:
        """Convert model to FrozenObject."""
        # print(f"from_object: {instance}")
        if instance is None:
            return instance
        obj_data = {
            "meta": {
                "frozen_at": tz_now(),
                "model": instance._meta.label,
                "id": instance.id,
                "fields": {},
                "deep_freeze": deep_freeze,
                "exclude": exclude,
            }
        }
        print(f"BEFORE: {obj_data}")
        for field in instance._meta.local_fields:
            if exclude and field.name in exclude:
                continue
            if isinstance(field, RelatedField) and not deep_freeze:
                obj_data["meta"]["exclude"].append(field.name)
                continue
            obj_data["meta"]["fields"][field.name] = (
                field.__class__.__module__,
                field.__class__.__qualname__,
            )
            value = getattr(instance, field.name)
            print(f">>> processing field {field}")
            # recursively serialize all FKs
            if isinstance(field, JSONField):
                print(f"..processing JSONField {field.name}:{value}")
                obj_data[field.name] = field.get_prep_value(value)
            elif isinstance(value, models.Model):
                print(f"..processing FK {field.name}:{value}")
                obj = cls.from_object(value)
                if obj:
                    obj_data[field.name] = obj.raw
            elif isinstance(value, cls):
                print(f"..processing FrozenObject {field.name}:{value}")
                obj_data[field.name] = value.raw
            else:
                print(f"..processing {field} {field.name}:{value}")
                obj_data[field.name] = field.get_prep_value(value)
            print(f"<<< output {obj_data[field.name]}")
        print(f"AFTER: {obj_data}")
        return FrozenObject(obj_data)
