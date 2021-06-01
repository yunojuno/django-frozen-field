from __future__ import annotations

import dataclasses

from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.utils.translation import gettext_lazy as _lazy

from frozen_data.models import freeze_object, unfreeze_object

from .types import AttributeList


class FrozenObjectField(models.JSONField):
    """Store snapshot of a model instance in a JSONField."""

    description = _lazy("A frozen representation of a FK model")

    def __init__(
        self,
        app_model: models.Model,
        include: AttributeList | None = None,
        exclude: AttributeList | None = None,
        select_related: AttributeList | None = None,
        **json_field_kwargs: object,
    ) -> None:
        """Initialise FrozenObjectField."""
        self.related_model = app_model
        self.include = include or []
        self.exclude = exclude or []
        self.select_related = select_related or []
        json_field_kwargs["encoder"] = DjangoJSONEncoder
        super().__init__(**json_field_kwargs)

    def deconstruct(self) -> tuple[str, str, list, dict]:
        name, path, args, kwargs = super().deconstruct()
        del kwargs["encoder"]
        args = ["app_model"]
        return name, path, args, kwargs

    def to_python(self, value: object) -> object | None:
        raise NotImplementedError(f"calling to_python with value='{value}'")

    def from_db_value(
        self, value: object, expression: object, connection: object
    ) -> object | None:
        """Deserialize db contents back into original model."""
        if value is None:
            return value
        value = super().from_db_value(value, expression, connection)
        return unfreeze_object(value)  # type: ignore [arg-type]

    def get_prep_value(self, value: object | None) -> dict | None:
        if value is None:
            return value

        if isinstance(value, models.Model):
            obj = freeze_object(
                value,
                include=self.include,
                exclude=self.exclude,
                select_related=self.select_related,
            )
            retval = super().get_prep_value(dataclasses.asdict(obj))
            return retval

        if dataclasses.is_dataclass(value):
            return dataclasses.asdict(value)

        raise NotImplementedError(f"calling get_prep_value with value='{value}'")
