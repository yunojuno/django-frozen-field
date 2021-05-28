from __future__ import annotations

from importlib import import_module
from typing import NoReturn

from django.db import models
from django.db.models.fields import Field
from django.utils.timezone import now as tz_now

from frozen_data.exceptions import FrozenAttribute, StaleObjectError
from frozen_data.fields import FrozenObjectField


class FrozenObject:
    """
    Container for an object that looks like a frozen model.

    This class id designed to manage the deserialization (unfreezing)
    of data in the following form:

        {
            "meta": {
                "label": "core.Address",
                "frozen_at": "2021-05-28T16:42:43.829687+00:00",
                "fields": {
                    "id": "django.db.models.IntegerField",
                    "line_1": "django.db.models.CharField",
                    "user": "frozen_data.models.FrozenObject"
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

    def __init__(self, frozen_data: dict) -> None:
        self.raw = frozen_data

    def __setattr__(self, name: str, value: object) -> None:
        """Prevent setting of frozen attributes."""
        # this is the first propert set, so must pass through
        if name == "raw":
            return super().__setattr__(name, value)
        # allow other arbitrary fields through if not in the frozen set
        if name not in self.fields:
            return super().__setattr__(name, value)
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
        try:
            field_klass = self.get_field(name)
        except KeyError:
            raise AttributeError(
                f"FrozenObject[{self.label}] has no attribute '{name}'"
            )
        else:
            value = self.raw[name]
            print(f"getting value {value} for field {field_klass}")
        if issubclass(field_klass, FrozenObjectField):
            # found nested FrozenObject
            return FrozenObject(value)
        if issubclass(field_klass, (models.ForeignKey, models.OneToOneField)):
            # found nested FK
            return FrozenObject(value)
        return field_klass().to_python(value)

    @property
    def label(self) -> str:
        """Return name of the model that is being frozen."""
        return self.raw["meta"]["label"]

    @property
    def fields(self):
        return self.raw["meta"]["fields"]

    def save(self, *args: object, **kwargs: object) -> NoReturn:
        raise StaleObjectError

    def get_field(self, name: str) -> Field:
        """Return the field represented by the name."""
        module, klass = self.fields[name]
        return getattr(import_module(module), klass)

    @classmethod
    def freeze(cls, instance: models.Model) -> dict:
        """Convert model to FrozenObject."""
        if instance is None:
            return instance
        obj_data = {
            "meta": {
                "frozen_at": tz_now(),
                "label": instance._meta.label,
                "id": instance.id,
                "fields": {},
            }
        }
        for field in instance._meta.local_fields:
            obj_data["meta"]["fields"][field.name] = (
                field.__class__.__module__,
                field.__class__.__qualname__,
            )
            value = getattr(instance, field.name)
            # recursively serialize all FKs
            if isinstance(
                field, (models.ForeignKey, models.OneToOneField, FrozenObjectField)
            ):
                obj_data[field.name] = cls.freeze(value).raw
            else:
                obj_data[field.name] = field.get_prep_value(value)
        return FrozenObject(obj_data)
