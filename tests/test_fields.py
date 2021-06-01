import uuid
from decimal import Decimal

import pytest
from django.utils.timezone import now as tz_now

from frozen_data.exceptions import FrozenObjectError

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
            # print(f"Checking {f}")
            assert getattr(nested.frozen, f.name) == getattr(nested.fresh, f.name)

    def test_nested(self, nested):
        nested.refresh_from_db()
        with pytest.raises(FrozenObjectError):
            nested.frozen.save()
        nested.fresh.save()

    def test_deep_nested(self, nested):
        deep_nested = DeepNestedModel.objects.create(fresh=nested, frozen=nested)
        deep_nested.refresh_from_db()
        assert deep_nested.fresh.id == deep_nested.frozen.id
        print(deep_nested.frozen.frozen)
        print(type(deep_nested.frozen.frozen))
        print(type(deep_nested.frozen))
        assert deep_nested.fresh.fresh.id == deep_nested.frozen.frozen.id
