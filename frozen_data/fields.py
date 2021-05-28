from __future__ import annotations

import json
from typing import NoReturn

from django.apps.registry import apps
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db.models.base import Model
from django.utils.translation import gettext_lazy as _lazy

from frozen_data.exceptions import StaleObjectError
from frozen_data.serializers import deserialize, serialize


def _raise_stale_object_error() -> NoReturn:
    """Patch model save method to raise StaleObjectError."""
    raise StaleObjectError


class FrozenObjectField(models.JSONField):
    """
    Store snapshot of a model instance in a JSONField.

    This field must be used in conjunction with the FrozenDataMixin class. The
    field behaves exactly like a FK field - you set/get the field as the object,
    but in the background it stores the object as a serialized snapshot. The object
    that you get back is deserialized from this snapshot, and cannot be saved itself,
    as this would overwrite newer data.

    """

    description = _lazy("A frozen representation of a FK model")

    def __init__(
        self,
        app_model: Model,
        *args: object,
        **kwargs: object,
    ) -> None:
        kwargs["encoder"] = DjangoJSONEncoder
        super().__init__(*args, **kwargs)
        self.app_model: Model = app_model

    def deconstruct(self) -> tuple[str, str, list, dict]:
        name, path, args, kwargs = super().deconstruct()
        args.insert(0, self.app_model)
        return name, path, args, kwargs

    def to_python(self, value: object) -> object | None:
        if value is None:
            return None

        if not isinstance(value, str):
            raise ValidationError(f"Unable to convert value to {self.app_model}")

        as_dict = json.loads(value)
        klass = as_dict["meta"]["model"].split(".")
        return deserialize(apps.get_model(*klass), **as_dict)

    def from_db_value(
        self, value: object, expression: object, connection: object
    ) -> object | None:
        """Deserialize db contents back into original model."""
        if not value:
            return None
        # as we subclass JSONField this will return a python dict
        _value = super().from_db_value(value, expression, connection)
        instance = deserialize(self.app_model, **_value)
        # HACK: patch save method with one that will prevent saving.
        instance.save = _raise_stale_object_error
        return instance

    def get_prep_value(self, value: object) -> dict | None:
        # JSONField expects a dict, so serialize the object first
        _value = serialize(value)
        # this dumps the dict using the DjangoJSONEncoder
        _value = super().get_prep_value(_value)
        # store the value back on the object - indicates that
        # we have serialized the object, and are about to save it.
        value._raw = _value
        return _value
