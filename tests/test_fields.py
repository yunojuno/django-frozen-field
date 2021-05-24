import uuid
from decimal import Decimal

import pytest
from django.utils.timezone import now as tz_now

from frozen_data.exceptions import StaleObjectError

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
        field_float=float(1),
        field_uuid=uuid.uuid4(),
    )


@pytest.fixture
def nested(flat):
    return NestedModel.objects.create(
        frozen=flat,
        current=flat,
    )


@pytest.mark.django_db
class TestFrozenDataField:
    def test_save(self, flat):
        flat.save()
        nested = NestedModel(frozen=flat, current=flat)
        nested.save()
        nested.refresh_from_db()

    def test_save__error(self, flat):
        flat.save()
        nested = NestedModel(frozen=flat, current=flat)
        nested.save()
        nested.refresh_from_db()
        with pytest.raises(StaleObjectError):
            nested.frozen.save()
        nested.current.save()
