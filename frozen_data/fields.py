from __future__ import annotations

import json
from typing import NoReturn

from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db.models.base import Model
from django.db.models.fields import Field
from django.db.models.fields.related import ForeignKey, OneToOneField
from django.utils.timezone import now as tz_now
from django.utils.translation import gettext_lazy as _lazy

from frozen_data.exceptions import StaleObjectError


class FrozenDataField(models.JSONField):
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
        deep_freeze: list[str] | None = None,
        **kwargs: object,
    ) -> None:
        kwargs["encoder"] = DjangoJSONEncoder
        super().__init__(*args, **kwargs)
        self.app_model: Model = app_model
        self.deep_freeze: list[str] = []

    def raise_stale(self) -> NoReturn:
        """Patch model save method to raise StaleObjectError."""
        raise StaleObjectError

    def get_model_field(self, field_name: str) -> Field:
        return self.app_model._meta.get_field(field_name)

    def _deserialize(self, **frozen_model_data: object) -> object:
        """
        Convert serialized data back to a clone of the original object.

        The JSON stored will have date, datetime, Decimal, UUID fields all saved
        as strings. In order to deserialize these values back into the expected
        type we use the original model field. e.g. if `date_created` is declared
        on the model as a `models.DateField`, the JSON will contain
        `{"date_created": "2021-05-05"}. In order to deserialize this correctly
        we lean on the destination field itself, using the `to_python` method to
        convert it back to a datetime.date.

            obj.date_created = DateField.to_python("2021-05-05")

        """
        obj_data = {}
        for k, v in frozen_model_data.items():
            try:
                field: Field = self.get_model_field(k)
            except FieldDoesNotExist:
                continue
            else:
                obj_data[k] = field.to_python(v)
        instance = self.app_model(**obj_data)
        # the properties below are added to the new instance - they do not
        # appear on the model, and are indicative of an unfrozen object.
        instance.frozen_at = frozen_model_data["frozen_at"]
        instance._raw = frozen_model_data
        # patch in a new save method that prevents overwriting current data
        instance.save = self.raise_stale
        return instance

    def _serialize(self, value: Model) -> dict | None:
        """Serialize a model to a dict."""
        if value is None:
            return value
        obj_data = {"frozen_at": tz_now()}
        for field in value._meta.local_fields:
            _val = getattr(value, field.name)
            if isinstance(field, (ForeignKey, OneToOneField)):
                if field.name in self.deep_freeze:
                    obj_data[field.name] = self._serialize(_val)
                else:
                    obj_data[f"{field.name}_id"] = _val.id if _val else None
            else:
                obj_data[field.name] = field.get_prep_value(_val)
        return obj_data

    def deconstruct(self) -> tuple[str, str, list, dict]:
        name, path, args, kwargs = super().deconstruct()
        args.insert(0, self.app_model)
        if self.deep_freeze:
            kwargs["deep_freeze"] = self.deep_freeze
        return name, path, args, kwargs

    def to_python(self, value: object) -> object | None:
        _value = super().to_python(value)

        if _value is None:
            return None

        if isinstance(_value, str):
            _value = json.loads(_value)

        if isinstance(_value, dict):
            return self._deserialize(**_value)

        raise ValidationError(f"Unable to convert value to {self.app_model}")

    def from_db_value(
        self, value: object, expression: object, connection: object
    ) -> object | None:
        if not value:
            return None
        _value = super().from_db_value(value, expression, connection)
        return self._deserialize(**_value)

    def get_prep_value(self, value: object) -> dict | None:
        # JSONField expects a dict, so serialize the object first
        _value = self._serialize(value)
        _value = super().get_prep_value(_value)
        return _value
