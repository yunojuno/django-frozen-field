import dataclasses
import json
import uuid
from decimal import Decimal

import pytest
from django.core.serializers.json import DjangoJSONEncoder
from django.utils.timezone import now as tz_now

from frozen_data.models import create_meta, freeze_object, unfreeze_object
from tests.models import FlatModel, NestedModel
from tests.test_fields import _flat

TEST_DATA = {
    "meta": {
        "model": "Address",
        "frozen_at": "2021-05-28T16:42:43.829687+00:00",
        "fields": {
            "id": "django.db.models.IntegerField",
            "line_1": "django.db.models.CharField",
            "line_2": "django.db.models.CharField",
            "postal_code": "django.db.models.CharField",
            "country": "django.db.models.CharField",
        },
        "exclude": ["country"],
        "include": [],
        "select_related": [],
        "select_properties": [],
    },
    "id": 1,
    "line_1": "29 Acacia Avenue",
    "line_2": "Nuttytown",
    "postal_code": "NT1",
}


@pytest.mark.django_db
class TestFrozenObjectMeta:
    @pytest.mark.parametrize(
        "include,exclude,include_out,exclude_out",
        [
            (
                [],
                [],
                [
                    "id",
                    "field_int",
                    "field_str",
                    "field_bool",
                    "field_date",
                    "field_datetime",
                    "field_decimal",
                    "field_float",
                    "field_uuid",
                    "field_json",
                ],
                [],
            ),
            (
                ["field_int"],
                [],
                ["field_int"],
                [
                    "id",
                    "field_str",
                    "field_bool",
                    "field_date",
                    "field_datetime",
                    "field_decimal",
                    "field_float",
                    "field_uuid",
                    "field_json",
                ],
            ),
            (
                [],
                ["field_int"],
                [
                    "id",
                    "field_str",
                    "field_bool",
                    "field_date",
                    "field_datetime",
                    "field_decimal",
                    "field_float",
                    "field_uuid",
                    "field_json",
                ],
                ["field_int"],
            ),
        ],
    )
    def test_create_meta(self, include, exclude, include_out, exclude_out):
        flat = FlatModel.objects.create(
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
        meta = create_meta(flat, include=include, exclude=exclude)
        assert meta.include == include_out
        assert meta.exclude == exclude_out


@pytest.mark.django_db
def test_create_frozen_object():
    flat_obj = _flat()
    frozen_obj = freeze_object(flat_obj)
    for f in frozen_obj.meta.include:
        assert getattr(flat_obj, f) == getattr(frozen_obj, f)
    for f in frozen_obj.meta.include:
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(frozen_obj, f, getattr(flat_obj, f))


@pytest.mark.django_db
def test_dump_frozen_object():
    flat_obj = _flat()
    flat_obj.refresh_from_db()
    nested_obj = NestedModel(fresh=flat_obj, frozen=flat_obj)
    nested_obj.save()
    frozen_obj = freeze_object(nested_obj, include=["frozen", "fresh"])
    as_dict = dataclasses.asdict(frozen_obj)


@pytest.mark.django_db
def test_load_frozen_object():
    flat_obj = _flat()
    nested_obj = NestedModel(fresh=flat_obj, frozen=flat_obj)
    nested_obj.save()
    frozen_obj = freeze_object(nested_obj, include=["frozen", "fresh"])
    as_dict = dataclasses.asdict(frozen_obj)
    raw = json.dumps(as_dict, cls=DjangoJSONEncoder)
    # print("raw", raw)
    refreshed = unfreeze_object(as_dict)
    # assert refreshed == frozen_obj
    # print(refreshed)
