import dataclasses
import uuid
from dataclasses import dataclass
from decimal import Decimal

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
        field_decimal=Decimal("3.142"),
        field_float=float(1),
        field_uuid=uuid.uuid4(),
        field_json={"foo": "bar"},
    )


def _nested(flat: FlatModel) -> NestedModel:
    return NestedModel.objects.create(
        frozen=flat,
        fresh=flat,
    )


@pytest.fixture
def flat():
    return _flat()


@pytest.fixture
def nested(flat):
    return _nested(flat)


@pytest.mark.django_db
class TestFrozenObjectField:
    def test_save(self, flat):
        flat.save()
        nested = NestedModel(frozen=flat, fresh=flat)
        assert nested.frozen.field_datetime == nested.frozen.field_datetime
        nested.save()
        nested.refresh_from_db()
        for f in FlatModel._meta.local_fields:
            if f.name == "field_datetime":
                continue
            assert getattr(nested.frozen, f.name) == getattr(nested.fresh, f.name)

    def test_nested(self, nested):
        assert isinstance(nested.fresh, FlatModel)
        assert isinstance(nested.frozen, FlatModel)
        nested.refresh_from_db()
        assert isinstance(nested.fresh, FlatModel)
        assert dataclasses.is_dataclass(nested.frozen)
        assert nested.frozen.__class__.__name__ == "FrozenFlatModel"

    def test_deep_nested(self, nested):
        deep_nested = DeepNestedModel.objects.create(fresh=nested, frozen=nested)
        deep_nested.refresh_from_db()
        assert deep_nested.fresh.id == deep_nested.frozen.id
        print(deep_nested.frozen.meta)
        print(deep_nested.frozen)
        print(type(deep_nested.frozen.frozen))
        print(type(deep_nested.frozen))
        assert deep_nested.fresh.fresh.id == deep_nested.frozen.frozen.id
