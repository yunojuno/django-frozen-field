from __future__ import annotations

import dataclasses
from typing import Callable

# mypy hints

# e.g. "tests.FlatModel"
ModelName = str
# e.g. "django.db.models.fields.DateField"
ModelClassPath = str
AttributeName = str
AttributeValue = object
AttributeList = list[AttributeName]
IsoTimestamp = str
# {"date_registered": "django.db.models.fields.DateField"}
MetaFieldMap = dict[AttributeName, ModelClassPath]
FrozenModel = object
# see https://docs.python.org/3/library/pickle.html#object.__reduce__
PickleReducer = tuple[Callable, tuple[dict]]
# function call return value
DeconstructTuple = tuple[str, str, list, dict]
# used to define functions that overwrite default field to_python
FieldConverter = Callable[[AttributeName], AttributeValue]
FieldConverterMap = dict[AttributeName, FieldConverter]


def klass_str(klass: object) -> ModelClassPath:
    """Return fully-qualified (namespaced) name for a class."""
    return f"{klass.__class__.__module__}.{klass.__class__.__qualname__}"


def is_dataclass_instance(obj: object, cls_name: str | None = None) -> bool:
    """
    Return True if obj is a dataclass - taken from docs.

    See https://docs.python.org/3/library/dataclasses.html#dataclasses.is_dataclass

    """
    is_instance = dataclasses.is_dataclass(obj) and not isinstance(obj, type)
    if cls_name:
        return is_instance and obj.__class__.__name__ == cls_name
    return is_instance
