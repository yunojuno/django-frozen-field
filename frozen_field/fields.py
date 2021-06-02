from __future__ import annotations

import dataclasses

from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.utils.translation import gettext_lazy as _lazy

from frozen_field.models import freeze_object, unfreeze_object

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
        kwargs["include"] = self.include
        kwargs["exclude"] = self.exclude
        kwargs["select_related"] = self.select_related
        args = ["app_model"]
        return name, path, args, kwargs

    def from_db_value(
        self, value: object, expression: object, connection: object
    ) -> object | None:
        """Deserialize db contents (json) back into original frozen dataclass."""
        if value is None:
            return value
        # use JSONField to convert from string to a dict
        if (obj := super().from_db_value(value, expression, connection)) is None:
            return obj
        return unfreeze_object(obj)

    def get_prep_value(self, value: object | None) -> dict | None:
        """Convert frozen dataclass to stringified dict for serialization."""
        if value is None:
            return value
        # use JSONField to convert dict to string
        return super().get_prep_value(dataclasses.asdict(value))

    def pre_save(self, model_instance: models.Model, add: bool) -> object:
        """Convert Django model to a frozen dataclass before saving it."""
        # I have been deep into the SQLUpdateCompiler to untangle what's going
        # on and it appears that the model_instance passed in to this function
        # is *not* the object being frozen, it's the parent / container. We need
        # to ensure that the object being serialized is the field value. :shrug:
        if model_instance is None:
            return None
        if (obj := getattr(model_instance, self.attname)) is None:
            return obj
        return freeze_object(
            obj,
            include=self.include,
            exclude=self.exclude,
            select_related=self.select_related,
        )
