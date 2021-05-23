import uuid
from decimal import Decimal

import pytest
from django.utils.timezone import now as tz_now

from frozen_data.mixins import FrozenDataMixin

from .models import FlatModel, NestedModel


@pytest.fixture
def flat():
    return FlatModel.objects.create(
        field_int=999,
        field_str="This is some text",
        field_bool=True,
        field_date=tz_now().date(),
        field_datetime=tz_now(),
        field_decimal=Decimal(3.141592654),
        field_uuid=uuid.uuid4(),
    )

@pytest.fixture
def nested(flat):
    return NestedModel.objects.create(
        frozen=flat,
        current=flat
    )

@pytest.mark.django_db
class TestFrozenDataMixin:
    def test_freeze_flat(self, flat):
        data = flat.freeze()
        assert data["field_int"] == flat.field_int
        assert data["field_str"] == flat.field_str
        assert data["field_bool"] == flat.field_bool
        assert data["field_date"] == flat.field_date.isoformat()
        assert data["field_datetime"] == flat.field_datetime.isoformat()
        assert data["field_decimal"] == str(flat.field_decimal)
        assert data["field_uuid"] == str(flat.field_uuid)
        assert data["frozen_at"]
        assert data["_id"] == flat.id
        assert data["_pk"] == flat.pk

    def test_freeze_nested(self, nested):
        data = nested.freeze()
        obj = NestedModel.unfreeze(**data)

    def test_unfreeze(self, flat):
        data = flat.freeze()
        obj = FlatModel.unfreeze(**data)
        assert obj.field_int == flat.field_int
        assert obj.field_str == flat.field_str
        assert obj.field_bool == flat.field_bool
        assert obj.field_date == flat.field_date
        assert obj.field_datetime == flat.field_datetime
        assert obj.field_decimal == flat.field_decimal
        assert obj.field_uuid == flat.field_uuid
        assert obj.frozen_at
        assert obj._id
        assert obj._pk
