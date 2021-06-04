import decimal
import uuid

import pytest
from django.utils.timezone import now as tz_now

from .models import DeepNestedModel, FlatModel, NestedModel


def _flat() -> FlatModel:
    return FlatModel.objects.create(
        field_int=999,
        field_str="This is some text",
        field_bool=True,
        field_date=tz_now().date(),
        field_datetime=tz_now(),
        field_decimal=decimal.Decimal("3.142"),
        field_float=float(1),
        field_uuid=uuid.uuid4(),
        field_json={"foo": "bar"},
    )


def _nested(flat: FlatModel) -> NestedModel:
    return NestedModel.objects.create(
        frozen=flat,
        fresh=flat,
    )


def _deep(nested: NestedModel) -> DeepNestedModel:
    return DeepNestedModel.objects.create(
        frozen=nested,
        fresh=nested,
    )


@pytest.fixture
def flat() -> FlatModel:
    return _flat()


@pytest.fixture
def nested(flat: FlatModel) -> NestedModel:
    return _nested(flat)


@pytest.fixture
def deep(nested: NestedModel) -> DeepNestedModel:
    return _deep(nested)
