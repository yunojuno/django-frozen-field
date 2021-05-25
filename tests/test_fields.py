import uuid
from decimal import Decimal

import pytest
from django.utils.timezone import now as tz_now

from frozen_data.exceptions import StaleObjectError

from .models import DeepNestedModel, FlatModel, NestedModel


@pytest.fixture
def flat():
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


@pytest.fixture
def nested(flat):
    return NestedModel.objects.create(
        frozen=flat,
        fresh=flat,
    )


@pytest.mark.django_db
class TestFrozenDataField:
    def test_save(self, flat):
        flat.save()
        nested = NestedModel(frozen=flat, fresh=flat)
        assert nested.frozen.field_datetime == nested.frozen.field_datetime
        nested.save()
        nested.refresh_from_db()
        # for f in FlatModel._meta.local_fields:
        #     # print(f"Checking {f}")
        #     assert getattr(nested.frozen, f.name) == getattr(nested.fresh, f.name)

    def test_nested(self, nested):
        nested.refresh_from_db()
        with pytest.raises(StaleObjectError):
            nested.frozen.save()
        nested.fresh.save()

    def test_deep_nested(self, nested):
        deep_nested = DeepNestedModel.objects.create(fresh=nested, frozen=nested)
        # print(f"OBJECT HAS BEEN SERIALIZED: {deep_nested.frozen._raw}")
        deep_nested.refresh_from_db()
        assert deep_nested.fresh == deep_nested.frozen
        assert deep_nested.fresh.fresh == deep_nested.frozen.frozen
