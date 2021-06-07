from __future__ import annotations

import pickle
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import pytest
import pytz

from frozen_field.serializers import (
    freeze_object,
    gather_fields,
    split_list,
    strip_dict,
    unfreeze_object,
)
from frozen_field.types import AttributeList, AttributeName, is_dataclass_instance

from .models import DeepNestedModel, FlatModel, NestedModel


def to_date(value: str) -> date:
    """Test field converter."""
    return datetime.strptime(value, "%Y-%m-%d").date()


TEST_DATA = {
    "meta": {
        "model": "tests.FlatModel",
        "fields": {
            "id": "django.db.models.fields.AutoField",
            "field_int": "django.db.models.fields.IntegerField",
            "field_str": "django.db.models.fields.TextField",
            "field_bool": "django.db.models.fields.BooleanField",
            "field_date": "django.db.models.fields.DateField",
            "field_datetime": "django.db.models.fields.DateTimeField",
            "field_decimal": "django.db.models.fields.DecimalField",
            "field_float": "django.db.models.fields.FloatField",
            "field_uuid": "django.db.models.fields.UUIDField",
            "field_json": "django.db.models.fields.json.JSONField",
        },
        "properties": ["is_bool", "today"],
        "frozen_at": "2021-06-04T18:10:30.549Z",
    },
    "id": 1,
    "field_int": 999,
    "field_str": "This is some text",
    "field_bool": True,
    "field_date": "2021-06-04",
    "field_datetime": "2021-06-04T18:10:30.548Z",
    "field_decimal": "3.142",
    "field_float": 1,
    "field_uuid": "6f09460c-c82b-4c8f-9d94-8828402da52e",
    "field_json": {"foo": "bar"},
    "is_bool": True,
    "today": "2021-06-01",
}


@pytest.mark.django_db
class TestSerialization:
    """Group together serialization functions."""

    def test_serialization(self, flat: FlatModel) -> None:
        nested = NestedModel.objects.create(frozen=None, fresh=flat)
        nested.refresh_from_db()
        assert nested.frozen is None
        nested.frozen = nested.fresh
        nested.save()

    def test_deserialization(self, nested: NestedModel) -> None:
        # object has been saved, but not refreshed - so still a Model
        assert isinstance(nested.fresh, FlatModel)
        assert is_dataclass_instance(nested.frozen, "FrozenFlatModel")
        nested.save()
        nested.refresh_from_db()
        assert isinstance(nested.fresh, FlatModel)
        # frozen field has been serialized and is now a FrozenObject
        assert is_dataclass_instance(nested.frozen, "FrozenFlatModel")
        assert nested.frozen.is_bool

    def test_deep_nested(self, nested: NestedModel) -> None:
        """Test the full round-trip (save/refresh) recursively."""
        nested.refresh_from_db()
        deep_nested = DeepNestedModel.objects.create(fresh=nested, frozen=nested)
        deep_nested.refresh_from_db()
        assert is_dataclass_instance(deep_nested.frozen, "FrozenNestedModel")
        assert is_dataclass_instance(deep_nested.frozen.frozen, "FrozenFlatModel")
        # "frozen.fresh" is included as it is defined in 'selected_related'.
        assert is_dataclass_instance(deep_nested.frozen.fresh, "FrozenFlatModel")
        assert is_dataclass_instance(deep_nested.fresh.frozen, "FrozenFlatModel")
        assert isinstance(deep_nested.fresh, NestedModel)
        assert isinstance(deep_nested.fresh.fresh, FlatModel)
        # finally we check we can resave the fields that now contain frozen objects
        deep_nested.save()
        deep_nested.refresh_from_db()

    def test_attr_chaining(self, flat: FlatModel) -> None:
        """Test deep serialization of partial fields."""
        print("Creating empty nested model")
        nested = NestedModel()
        print("Setting fresh value")
        nested.fresh = flat
        print("Setting frozen value")
        nested.frozen = flat
        print("Creating empty deep nested model")
        deep = DeepNestedModel()
        print("Setting fresh value")
        deep.fresh = nested
        print("Setting frozen value")
        deep.frozen = nested
        print(f"deep.fresh: '{deep.fresh}'")
        print(f"deep.frozen: '{deep.frozen}'")
        print(deep.frozen.json_data())
        # deep.refresh_from_db()
        # assert deep.partial.fresh.json_data() == {"field_int": 999}


@pytest.mark.parametrize(
    "input,field_name,output",
    [
        ({}, "foo", {}),
        ({"foo": 1}, "foo", {}),
        ({"foo__bar": 1}, "foo", {"bar": 1}),
        ({"foo__bar__baz": 1}, "foo", {"bar__baz": 1}),
        ({"bar__foo__baz": 1}, "foo", {}),
        (
            {"foo": 1, "foo__bar": 2, "foo__bar__baz": 3},
            "foo",
            {"bar": 2, "bar__baz": 3},
        ),
    ],
)
def test_strip_dict(input: dict, field_name: AttributeName, output: dict) -> None:
    assert strip_dict(input, field_name) == output


@pytest.mark.parametrize(
    "input,output",
    [
        ([""], []),
        (["foo"], ["foo"]),
        (["foo__bar"], ["foo"]),
        (["foo", "foo__bar", "foo__bar__baz"], ["foo"]),
    ],
)
def test_split_list(input: AttributeList, output: AttributeList) -> None:
    assert split_list(input) == output


@pytest.mark.django_db
@pytest.mark.parametrize(
    "include,exclude,select_related,result",
    [
        ([], [], [], ["id", "frozen"]),
        (["id"], [], [], ["id"]),
        ([], ["id"], [], ["frozen"]),
        ([], ["id"], ["fresh"], ["frozen", "fresh"]),
        (["id"], [], ["fresh"], ["id", "fresh"]),
        ([], [], ["fresh"], ["id", "frozen", "fresh"]),
        (["fresh__id"], [], [], ["fresh"]),
    ],
)
def test_gather_fields(
    include: AttributeList,
    exclude: AttributeList,
    select_related: AttributeList,
    result: AttributeList,
) -> None:
    fields = gather_fields(NestedModel, include, exclude, select_related)
    assert [f.name for f in fields] == result


@pytest.mark.django_db
class TestFreezeObject:
    """Group together tests for freeze / unfreeze functions."""

    def test_freeze_object__none(self) -> None:
        assert freeze_object(None) is None

    def test_freeze_object(self, flat: FlatModel) -> None:
        frozen_obj = freeze_object(flat)
        assert frozen_obj is not None
        assert is_dataclass_instance(frozen_obj, "FrozenFlatModel")
        for f in frozen_obj.meta.frozen_attrs:  # type:ignore [attr-defined]
            assert getattr(flat, f) == getattr(frozen_obj, f)
        assert isinstance(flat.today, date)

    def test_unfreeze_object(self) -> None:
        assert unfreeze_object(None) is None
        obj = unfreeze_object(TEST_DATA.copy())
        assert obj is not None
        assert is_dataclass_instance(obj, "FrozenFlatModel")
        assert obj.id == 1  # type:ignore [attr-defined]
        assert obj.field_int == 999  # type:ignore [attr-defined]
        assert obj.field_str == "This is some text"  # type:ignore [attr-defined]
        assert obj.field_bool is True  # type:ignore [attr-defined]
        assert obj.field_date == date(2021, 6, 4)  # type:ignore [attr-defined]
        assert obj.field_datetime == datetime(  # type:ignore [attr-defined]
            2021, 6, 4, 18, 10, 30, 548000, tzinfo=pytz.UTC
        )
        assert obj.field_decimal == Decimal("3.142")  # type:ignore [attr-defined]
        assert obj.field_float == float(1)  # type:ignore [attr-defined]
        assert obj.field_uuid == UUID(  # type:ignore [attr-defined]
            "6f09460c-c82b-4c8f-9d94-8828402da52e"
        )
        assert obj.field_json == {"foo": "bar"}  # type:ignore [attr-defined]
        assert obj.is_bool is True  # type:ignore [attr-defined]
        assert obj.today == "2021-06-01"  # type:ignore [attr-defined]

    def test_unfreeze_object__converters(self) -> None:
        # default unfreeze returns 'today' as a string - as it has no associated field
        obj = unfreeze_object(TEST_DATA.copy())
        assert obj.today == "2021-06-01"  # type:ignore [attr-defined]
        # passing in a converter gets around this
        obj = unfreeze_object(TEST_DATA.copy(), {"today": to_date})
        assert obj.today == date(2021, 6, 1)  # type:ignore [attr-defined]


@pytest.mark.django_db
def test_pickle_frozen_object(flat: FlatModel) -> None:
    frozen = freeze_object(flat)
    p = pickle.dumps(frozen)
    q = pickle.loads(p)
    assert q == frozen
