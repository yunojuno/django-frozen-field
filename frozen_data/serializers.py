from __future__ import annotations

from django.apps import apps
from django.core.exceptions import FieldDoesNotExist
from django.db import models
from django.utils.timezone import now as tz_now


def get_model_field(app_model: models.Model, field_name: str) -> models.Field:
    """Return a model's Field object from its name."""
    return app_model._meta.get_field(field_name)


def deserialize(app_model: models.Model, **frozen_model_data: object) -> object:
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
    # print(f"Attempting to deserialize:")
    # print(json.dumps(frozen_model_data, indent=4))
    obj_data = {}
    for k, v in frozen_model_data.items():
        try:
            field: models.Field = get_model_field(app_model, k)
            # print(f"Deserializing field: {field}")
        except FieldDoesNotExist:
            continue
        else:
            if isinstance(field, (models.ForeignKey, models.OneToOneField)):
                # print(f"Deserializing FK from {v}")
                klass = apps.get_model(*v["meta"]["model"].split("."))
                # print(f"Deserializing FK into {klass}")
                obj_data[k] = deserialize(klass, **v)
            else:
                obj_data[k] = field.to_python(v)
    instance = app_model(**obj_data)
    # the properties below are added to the new instance - they do not
    # appear on the model, and are indicative of an unfrozen object.
    instance.frozen_at = frozen_model_data["meta"]["frozen_at"]
    instance._raw = frozen_model_data
    return instance


def serialize(value: models.Model) -> dict | None:
    """Serialize a model to a dict."""
    if value is None:
        return value
    obj_data = {
        "meta": {"frozen_at": tz_now(), "model": value._meta.label, "id": value.id}
    }
    for field in value._meta.local_fields:
        _val = getattr(value, field.name)
        # recursively serialize all FKs
        if isinstance(field, (models.ForeignKey, models.OneToOneField)):
            obj_data[field.name] = serialize(_val)
        else:
            obj_data[field.name] = field.get_prep_value(_val)
    return obj_data
