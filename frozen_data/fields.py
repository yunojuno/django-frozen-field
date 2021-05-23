from __future__ import annotations

import json
from typing import TYPE_CHECKING

from django.db import models
from django.db.models.base import Model
from django.utils.translation import gettext_lazy as _lazy

if TYPE_CHECKING:
    from .mixins import FrozenDataMixin


class FrozenDataField(models.JSONField):
    """
    Store snapshot of a model instance in a JSONField.

    This field must be used in conjunction with the FrozenDataMixin class. The
    field behaves exactly like a FK field - you set/get the field as the object,
    but in the background it stores the object as a serialized snapshot. The object
    that you get back is deserialized from this snapshot, and cannot be saved itself,
    as this would overwrite newer data.

        >>> address = Address.objects.last()
        >>> test = TestFrozenData(address=address)
        >>> test.save()
        >>> test.refresh_from_db()
        >>> assert test.address == address
        >>> test.address.save()
        StaleObjectError: Defrosted objects cannot be saved.
        >>> test.address.serialized_at
        '2021-05-23T11:51:39.961342+00:00'

    """

    description = _lazy("A frozen representation of a FK model")

    def __init__(self, app_model: Model, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.app_model = app_model

    def deconstruct(self) -> tuple[str, str, object, object]:
        name, path, args, kwargs = super().deconstruct()
        args.insert(0, self.app_model)
        return name, path, args, kwargs

    def from_db_value(
        self, value: object, expression: object, connection: object
    ) -> FrozenDataMixin | None:
        _value = super().from_db_value(value, expression, connection)
        if not value:
            return None
        return self.app_model.unfreeze(**_value)

    def to_python(self, value: object) -> FrozenDataMixin | None:
        _value = super().to_python(value)

        if _value is None:
            return None

        if isinstance(_value, str):
            return self.app_model.unfreeze(**json.loads(_value))

        if isinstance(_value, dict):
            return self.app_model.unfreeze(**_value)

        return _value

    def get_prep_value(self, value: FrozenDataMixin) -> dict:
        # JSONField expects a dict, so serialize the object first
        _value = value.freeze()
        return super().get_prep_value(_value)
