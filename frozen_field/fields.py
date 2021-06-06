from __future__ import annotations

import dataclasses
import logging

from django.apps import apps
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.utils.translation import gettext_lazy as _lazy

from .serializers import freeze_object, unfreeze_object
from .types import (
    AttributeList,
    DeconstructTuple,
    FieldConverterMap,
    FrozenModel,
    is_dataclass_instance,
)

logger = logging.getLogger(__name__)


class FrozenObjectField(models.JSONField):
    """Store snapshot of a model instance in a JSONField."""

    description = _lazy("A frozen representation of a FK model")

    def __init__(
        self,
        model: models.Model | str,
        include: AttributeList | None = None,
        exclude: AttributeList | None = None,
        select_related: AttributeList | None = None,
        select_properties: AttributeList | None = None,
        converters: FieldConverterMap | None = None,
        **json_field_kwargs: object,
    ) -> None:
        """
        Initialise FrozenObjectField.

        The model argument can be a Model itself, or the "app.Model" path to
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

        The select_properties argument is a list of model properties (not fields) that
        will be added to the serialized output.

        The converters argument is a mapping of field_name to a callable that can be
        used to convert the JSON representation to python during deserialization. By
        default fields use the underlying field.to_python method, but this doesn't
        always work, so this provides an override mechanism.

        The remaining kwargs are passed directly to the JSONField.

        """
        if not model:
            raise ValueError("Missing model argument.")
        if isinstance(model, type(models.Model)):
            self.model_label = model._meta.label
            self.model_name = model._meta.label.rsplit(".", 1)[-1]
        elif isinstance(model, str):
            self.model_label = model
            self.model_name = model.rsplit(".", 1)[-1]
        else:
            raise ValueError("Invalid model argument - must be a str or Model.")
        self.include = include or []
        self.exclude = exclude or []
        self.select_related = select_related or []
        self.select_properties = select_properties or []
        self.converters = converters or {}
        json_field_kwargs.setdefault("encoder", DjangoJSONEncoder)
        super().__init__(**json_field_kwargs)

    @property
    def frozen_model_name(self) -> str:
        return f"Frozen{self.model_name}"

    @property
    def model_klass(self) -> type[models.Model]:
        """Return Model type - it may have been set as a str."""
        return apps.get_model(*self.model_label.split("."))

    def deconstruct(self) -> DeconstructTuple:
        name, path, args, kwargs = super().deconstruct()
        if kwargs["encoder"] == DjangoJSONEncoder:
            del kwargs["encoder"]
        kwargs["include"] = self.include
        kwargs["exclude"] = self.exclude
        kwargs["select_related"] = self.select_related
        kwargs["select_properties"] = self.select_properties
        kwargs["converters"] = self.converters
        args = [self.model_label]
        return name, path, args, kwargs

    def from_db_value(
        self, value: str | None, expression: object, connection: object
    ) -> FrozenModel | None:
        """Deserialize db contents (json) back into original frozen dataclass."""
        logger.debug("--> Deserializing frozen object from '%s'", value)
        if value is None:
            return value
        # use JSONField to convert from string to a dict
        if obj := super().from_db_value(value, expression, connection):
            return unfreeze_object(obj, self.converters)
        return None

    def get_prep_value(self, value: FrozenModel | None) -> dict | None:
        """Convert frozen dataclass to stringified dict for serialization."""
        logger.debug("--> FrozenObjectField.get_prep_value: '%r'", value)
        if value is None:
            return value
        # use JSONField to convert dict to string
        return super().get_prep_value(dataclasses.asdict(value))

    def pre_save(self, model_instance: models.Model, add: bool) -> FrozenModel | None:
        """
        Convert Django model to a frozen dataclass before saving it.

        The model_instance argument is the model to which we have attached the field,
        and so before saving we need to extract the value of the field itself using
        the `attname` property.

        If the value of the field is a model of the expected type, we freeze it. If it
        is already frozen, we just pass it back again.

        """
        logger.debug("--> FrozenObjectField.pre_save: '%r'", model_instance)
        if (obj := getattr(model_instance, self.attname)) is None:
            logger.debug("--> field value is empty")
            return obj
        if is_dataclass_instance(obj, self.frozen_model_name):
            logger.debug("--> field value is already frozen")
            return obj
        if isinstance(obj, self.model_klass):
            logger.debug("--> freezing field value: '%r'", obj)
            return freeze_object(
                obj,
                include=self.include,
                exclude=self.exclude,
                select_related=self.select_related,
                select_properties=self.select_properties,
            )
        raise ValueError(f"model_instance '{self.attname}' value is invalid.")
