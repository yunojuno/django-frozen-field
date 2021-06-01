from __future__ import annotations

import dataclasses

from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.utils.translation import gettext_lazy as _lazy

from frozen_data.models import freeze_object


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
        app_model: models.Model,
        include: list[str] | None = None,
        exclude: list[str] | None = None,
        **json_field_kwargs: object
    ) -> None:
        """
        Initialise FrozenObjectField.

        If deep_freeze is True then related objects are serialized. This can
            cause recursion errors, and is False by default.
        The `exclude` list is a list of field names in the object that you can
            be ignored.

        """
        self.related_model = app_model
        self.include = include or []
        self.exclude = exclude or []
        json_field_kwargs["encoder"] = DjangoJSONEncoder
        super().__init__(**json_field_kwargs)

    def deconstruct(self) -> tuple[str, str, list, dict]:
        name, path, args, kwargs = super().deconstruct()
        del kwargs["encoder"]
        args = ["app_model"]
        return name, path, args, kwargs

    def to_python(self, value: object) -> object | None:
        raise NotImplementedError

    def from_db_value(
        self, value: object, expression: object, connection: object
    ) -> object | None:
        """Deserialize db contents back into original model."""
        raise NotImplementedError

    def get_prep_value(self, value: object | None) -> dict | None:
        # JSONField expects a dict, so serialize the object first
        if value is None:
            return value

        if isinstance(value, models.Model):
            value = freeze_object(value, include=self.include, exclude=self.exclude)

        return super().get_prep_value(dataclasses.asdict(value))
