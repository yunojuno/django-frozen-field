from __future__ import annotations

import json
from typing import cast

from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db.models.base import Model
from django.utils.translation import gettext_lazy as _lazy

from frozen_data.models import FrozenObject


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
        *args: object,
        deep_freeze: bool = False,
        exclude: list[str] | None = None,
        **kwargs: object,
    ) -> None:
        """
        Initialise FrozenObjectField.

        If deep_freeze is True then related objects are serialized. This can
            cause recursion errors, and is False by default.
        The `exclude` list is a list of field names in the object that you can
            be ignored.

        """
        self.deep_freeze = deep_freeze
        self.exclude = exclude or []
        kwargs["encoder"] = DjangoJSONEncoder
        super().__init__(*args, **kwargs)

    def deconstruct(self) -> tuple[str, str, list, dict]:
        name, path, args, kwargs = super().deconstruct()
        del kwargs["encoder"]
        return name, path, args, kwargs

    def to_python(self, value: object) -> FrozenObject | None:
        if value is None:
            return None

        from .models import FrozenObject  # noqa: circ import

        if isinstance(value, FrozenObject):
            return value

        return FrozenObject(cast(dict, value))

    def from_db_value(
        self, value: object, expression: object, connection: object
    ) -> object | None:
        """Deserialize db contents back into original model."""
        if value is None:
            return value

        # print(f"DESERIALIZING FROM {value}")
        if not isinstance(value, str):
            raise Exception("Invalid from_db_value")
        frozen_data = json.loads(value)
        return FrozenObject(frozen_data)

    def get_prep_value(self, value: Model | FrozenObject | None) -> dict | None:
        # JSONField expects a dict, so serialize the object first
        if value is None:
            return value

        # print(f"GET_PREP_VALUE for: {value}")
        # from .models import FrozenObject
        if isinstance(value, models.Model):
            value = FrozenObject.from_object(
                value,
                deep_freeze=self.deep_freeze,
                exclude=self.exclude,
            )

        # if it's not a model we assume it is a FrozenObject already
        # print(f"SERIALIZING: {value}")
        value = super().get_prep_value(value.raw)
        # print(f"SERIALIZED AS: {value}")
        return value
