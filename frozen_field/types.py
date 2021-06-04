from __future__ import annotations

import dataclasses
from typing import Callable

# mypy hints
ModelName = str
ModelKlass = str
AttributeName = str
AttributeList = list[AttributeName]
IsoTimestamp = str
MetaFields = dict[AttributeName, ModelKlass]
# this looks useless, but helps keep function in/out aligned
FrozenModel = object
# see https://docs.python.org/3/library/pickle.html#object.__reduce__
PickleReducer = tuple[Callable, tuple[dict]]
# function call return value
DeconstructTuple = tuple[str, str, list, dict]


def klass_str(klass: object) -> ModelKlass:
    """Return fully-qualified (namespaced) name for a class."""
    return f"{klass.__class__.__module__}.{klass.__class__.__qualname__}"


def is_dataclass_instance(obj: object, cls_name: str) -> bool:
    """
    Return True if obj is a dataclass - taken from docs.

    See https://docs.python.org/3/library/dataclasses.html#dataclasses.is_dataclass

    """
    return (
        dataclasses.is_dataclass(obj)
        and not isinstance(obj, type)
        and obj.__class__.__name__ == cls_name
    )
