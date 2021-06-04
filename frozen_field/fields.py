from __future__ import annotations

import dataclasses

from django.apps import apps
from django.core.exceptions import ValidationError
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
        source_model: models.Model | str,
        include: AttributeList | None = None,
        exclude: AttributeList | None = None,
        select_related: AttributeList | None = None,
        **json_field_kwargs: object,
    ) -> None:
        """
        Initialise FrozenObjectField.

        The source_model argument can be a Model itself, or the "app.Model" path to
        a model (supported in case of circ. import issues).

        The include argument is a list of fields on the app_model used to
        restrict which fields are serialized. The default (None) is to include
        every non-related field on the model.

        The exclude argument is a list of fields on the app_model to exclude from
        serialization. It can only be used if include is None.

        The select_related argument is a list of related fields (ForeignKey, OneToOne)
        to include in the serialization. By default all related fields are ignored.
        This list is appended to the include list when considering which fields to
        serialize.

        The remaining kwargs are passed directly to the JSONField.

        """
        self.source_model = source_model
        self.include = include or []
        self.exclude = exclude or []
        self.select_related = select_related or []
        json_field_kwargs.setdefault("encoder", DjangoJSONEncoder)
        super().__init__(**json_field_kwargs)

    @property
    def model_klass(self) -> type[models.Model]:
        """Return self.source_model as a Model type - it may have been set as a str."""
        if not self.source_model:
            raise ValueError("FrozenObjectField model is undefined")
        if isinstance(self.source_model, str):
            return apps.get_model(*self.source_model.split("."))
        if issubclass(self.source_model, models.Model):
            return self.source_model
        raise ValueError(
            f"Invalid FrozenObjectField model [{self.source_model}] - "
            "must be a str or Model"
        )

    def validate_model(self, obj: models.Model) -> None:
        """Validate that model instance is the correct / expected type."""
        if not isinstance(obj, self.model_klass):
            raise ValidationError(
                f"Invalid model instance; expected '{self.source_model}', got '{obj}'."
            )

    def deconstruct(self) -> tuple[str, str, list, dict]:
        name, path, args, kwargs = super().deconstruct()
        kwargs["include"] = self.include
        kwargs["exclude"] = self.exclude
        kwargs["select_related"] = self.select_related
        args = [self.source_model]
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
        self.validate_model(obj)
        return freeze_object(
            obj,
            include=self.include,
            exclude=self.exclude,
            select_related=self.select_related,
        )
