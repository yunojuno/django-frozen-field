from __future__ import annotations

import pickle
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from unittest import mock
from uuid import UUID

import freezegun
import pytest
import pytz

from frozen.serializers import (
    freeze_object,
    gather_fields,
    split_list,
    strip_dict,
    unfreeze_object,
)
from frozen.types import AttributeList, AttributeName, is_dataclass_instance

from .models import DeepNestedModel, FlatModel, NestedModel


def to_date(value: str) -> date:
    """Test field converter."""
    return datetime.strptime(value, "%Y-%m-%d").date()


TEST_DATA = {
    "_meta": {
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


@pytest.mark.django_db
@freezegun.freeze_time()
@mock.patch("frozen.fields.freeze_object")
def test_deep_freeze(mock_freeze: mock.Mock) -> None:
    """
    Test deep serialization of partial fields.

    This test mocks out the actual freezing so that we can follow
    the exact chain of calls.

    """
    # now = tz_now()
    flat = FlatModel()
    _ = NestedModel(frozen=flat)
    assert mock_freeze.call_count == 1

    mock_freeze.reset_mock()
    _ = NestedModel(fresh=flat)
    assert mock_freeze.call_count == 0

    mock_freeze.reset_mock()
    _ = NestedModel(fresh=flat, frozen=flat)
    assert mock_freeze.call_count == 1

    mock_freeze.reset_mock()
    _ = DeepNestedModel(fresh=NestedModel())
    assert mock_freeze.call_count == 0

    mock_freeze.reset_mock()
    _ = DeepNestedModel(fresh=NestedModel(frozen=flat))
    assert mock_freeze.call_count == 1

    mock_freeze.reset_mock()
    _ = DeepNestedModel(frozen=NestedModel())
    assert mock_freeze.call_count == 1

    # freeze deep.frozen.frozen, and deep.frozen
    mock_freeze.reset_mock()
    deep = DeepNestedModel(frozen=NestedModel(frozen=flat))
    assert mock_freeze.call_count == 2
    assert isinstance(mock_freeze.call_args_list[0][0][0], FlatModel)
    assert isinstance(mock_freeze.call_args_list[1][0][0], NestedModel)

    # nothing to freeze - partial and frozen attrs are empty
    mock_freeze.reset_mock()
    deep = DeepNestedModel(fresh=NestedModel())
    assert mock_freeze.call_count == 0
    assert deep.fresh.fresh is None
    assert deep.fresh.frozen is None
    assert deep.frozen is None
    assert deep.partial is None  # type:ignore [unreachable]

    mock_freeze.reset_mock()
    deep.frozen = NestedModel()
    assert mock_freeze.call_count == 1
    deep.partial == deep.frozen
    assert mock_freeze.call_count == 1

    mock_freeze.reset_mock()
    deep.frozen = NestedModel()
    assert mock_freeze.call_count == 1
    deep.partial == deep.frozen
    assert mock_freeze.call_count == 1


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
        frozen_obj: Any = freeze_object(flat)
        assert frozen_obj is not None
        assert is_dataclass_instance(frozen_obj, "FrozenFlatModel")
        for f in frozen_obj._meta.frozen_attrs:
            assert getattr(flat, f) == getattr(frozen_obj, f)
        assert isinstance(flat.today, date)

    def test_unfreeze_object(self) -> None:
        assert unfreeze_object(None) is None
        obj: Any = unfreeze_object(TEST_DATA.copy())
        assert obj is not None
        assert is_dataclass_instance(obj, "FrozenFlatModel")
        assert obj.id == 1
        assert obj.field_int == 999
        assert obj.field_str == "This is some text"
        assert obj.field_bool is True
        assert obj.field_date == date(2021, 6, 4)
        assert obj.field_datetime == datetime(
            2021, 6, 4, 18, 10, 30, 548000, tzinfo=pytz.UTC
        )
        assert obj.field_decimal == Decimal("3.142")
        assert obj.field_float == float(1)
        assert obj.field_uuid == UUID("6f09460c-c82b-4c8f-9d94-8828402da52e")
        assert obj.field_json == {"foo": "bar"}
        assert obj.is_bool is True
        assert obj.today == "2021-06-01"

    def test_unfreeze_object__converters(self) -> None:
        # default unfreeze returns 'today' as a string - as it has no associated field
        obj: Any = unfreeze_object(TEST_DATA.copy())
        assert obj.today == "2021-06-01"
        # passing in a converter gets around this
        obj = unfreeze_object(TEST_DATA.copy(), {"today": to_date})
        assert obj.today == date(2021, 6, 1)

    def test_real_example(self) -> None:
        """Test deep unfreeze."""
        test_uuid = uuid.uuid4().hex
        data = {
            "_meta": {
                "model": "test.Foo",
                "fields": {
                    "uuid": "django.db.models.fields.UUIDField",
                    "bar": "django.db.models.fields.related.ForeignKey",
                    "empty": "django.db.models.fields.related.ForeignKey",
                },
                "frozen_at": "2021-06-09T09:08:30.736Z",
            },
            "uuid": test_uuid,
            "empty": None,
            "bar": {
                "_meta": {
                    "model": "test.Bar",
                    "fields": {
                        "uuid": "django.db.models.fields.UUIDField",
                        "baz": "django.db.models.fields.related.ForeignKey",
                    },
                    "frozen_at": "2021-06-09T09:08:30.773Z",
                    "properties": [],
                },
                "uuid": test_uuid,
                "baz": {
                    "_meta": {
                        "model": "test.Baz",
                        "fields": {
                            "uuid": "django.db.models.fields.UUIDField",
                        },
                        "frozen_at": "2021-06-09T09:08:30.773Z",
                        "properties": [],
                    },
                    "uuid": test_uuid,
                },
            },
        }
        original_data = data.copy()
        obj: Any = unfreeze_object(data)
        assert data == original_data
        assert obj.empty is None
        assert obj._meta.model == "test.Foo"
        assert obj.bar._meta.model == "test.Bar"
        assert obj.bar.baz._meta.model == "test.Baz"
        assert obj.uuid == obj.bar.uuid == obj.bar.baz.uuid == UUID(test_uuid)


@pytest.mark.django_db
def test_pickle_frozen_object(flat: FlatModel) -> None:
    frozen = freeze_object(flat)
    p = pickle.dumps(frozen)
    q = pickle.loads(p)
    assert q == frozen
