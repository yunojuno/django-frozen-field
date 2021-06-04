import dataclasses
import json
import pickle
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

import freezegun
import pytest
import pytz
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db.models.fields import (
    BooleanField,
    DateField,
    DateTimeField,
    DecimalField,
    FloatField,
    IntegerField,
    SmallIntegerField,
    TextField,
    UUIDField,
)
from django.db.models.fields.json import JSONField
from django.utils.timezone import now as tz_now

from frozen_field.models import (
    FrozenObjectMeta,
    _gather_fields,
    create_meta,
    freeze_object,
    unfreeze_object,
)
from frozen_field.types import AttributeList, is_dataclass_instance
from tests.models import FlatModel, NestedModel

TEST_NOW = tz_now()

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
}


@pytest.mark.django_db
class TestFrozenObjectMeta:
    def test_cls_name(self) -> None:
        meta = FrozenObjectMeta(
            model="tests.FlatModel",
            fields={},
            frozen_at=tz_now(),
        )
        assert meta.cls_name == "FrozenFlatModel"

    @pytest.mark.parametrize(
        "fields,frozen_attrs",
        [
            ({}, []),
            ({"foo": 1}, ["foo"]),
            ({"foo": 1, "bar": False}, ["foo", "bar"]),
        ],
    )
    def test_frozen_attrs(self, fields, frozen_attrs) -> None:
        meta = FrozenObjectMeta(
            model="tests.FlatModel",
            fields=fields,
            frozen_at=tz_now(),
        )
        assert meta.frozen_attrs == frozen_attrs

    @pytest.mark.parametrize(
        "value,has_meta",
        [
            ({}, False),
            ({"foo": 1}, False),
            ({"meta": {}}, False),
            ({"meta": {"frozen_at": tz_now()}}, True),
        ],
    )
    def test_has_meta(self, value: dict, has_meta: bool) -> None:
        assert FrozenObjectMeta.has_meta(value) == has_meta

    def test_make_dataclass(self) -> None:
        meta = FrozenObjectMeta(
            "tests.FlatModel",
            {"field_int": "django.db.models.fields.IntegerField"},
            frozen_at=tz_now(),
        )
        klass = meta.make_dataclass()
        assert [f.name for f in dataclasses.fields(klass)] == ["meta", "field_int"]
        obj1 = klass(meta, 999)
        assert obj1.data() == {"field_int": 999}
        assert obj1.__module__ == "frozen_field.models"
        with pytest.raises(dataclasses.FrozenInstanceError):
            obj1.field_int = 0

        obj2 = klass(meta, 999)
        assert obj1 == obj2
        obj3 = klass(meta, 998)
        assert obj1 != obj3

    def test_parse_obj(self) -> None:
        flat = FlatModel(field_int=999)
        meta = FrozenObjectMeta(
            "tests.FlatModel",
            {"field_int": "django.db.models.fields.IntegerField"},
            frozen_at=tz_now(),
        )
        assert meta.parse_obj(flat) == {"field_int": 999}

    def test_parse_obj__value_error(self) -> None:
        """Test that the meta.model matches the model being parsed."""
        flat = FlatModel(field_int=999)
        meta = FrozenObjectMeta(
            "tests.FlatMdoel",
            {"field_int": "django.db.models.fields.IntegerField"},
            frozen_at=tz_now(),
        )
        with pytest.raises(ValueError):
            meta.parse_obj(flat)

    def test_parse_obj__error(self, flat: FlatModel) -> None:
        nested = NestedModel()
        meta = create_meta(FlatModel)
        assert meta is not None
        with pytest.raises(ValueError):
            _ = meta.parse_obj(nested)

    @pytest.mark.parametrize(
        "field_path,field_klass",
        [
            ("django.db.models.fields.IntegerField", IntegerField),
            ("django.db.models.fields.TextField", TextField),
            ("django.db.models.fields.BooleanField", BooleanField),
            ("django.db.models.fields.DateField", DateField),
            ("django.db.models.fields.DateTimeField", DateTimeField),
            ("django.db.models.fields.DecimalField", DecimalField),
            ("django.db.models.fields.FloatField", FloatField),
            ("django.db.models.fields.UUIDField", UUIDField),
            ("django.db.models.fields.json.JSONField", JSONField),
        ],
    )
    def test__field(self, field_path, field_klass) -> None:
        meta = FrozenObjectMeta(
            model="tests.FlatModel",
            fields={"test_field": field_path},
            frozen_at=None,
        )
        assert isinstance(meta._field("test_field"), field_klass)

    @pytest.mark.parametrize(
        "field_path,input,output",
        [
            (
                "django.db.models.fields.IntegerField",
                1,
                1,
            ),  # easy one to start off with
            ("django.db.models.fields.DecimalField", "1", Decimal(1.0)),
            ("django.db.models.fields.FloatField", "1", float(1)),
            ("django.db.models.fields.DateField", "2021-06-01", date(2021, 6, 1)),
            (
                "django.db.models.fields.DateTimeField",
                "2021-06-01T15:38:44.277Z",
                datetime(2021, 6, 1, 15, 38, 44, 277000, tzinfo=pytz.UTC),
            ),
            (
                "django.db.models.fields.UUIDField",
                "ee2658f6-632c-4e2b-96b2-7c68e7421afe",
                UUID("ee2658f6-632c-4e2b-96b2-7c68e7421afe"),
            ),
            (
                "django.db.models.fields.UUIDField",
                "ee2658f6632c4e2b96b27c68e7421afe",
                UUID("ee2658f6-632c-4e2b-96b2-7c68e7421afe"),
            ),
            (
                "django.db.models.fields.UUIDField",
                "EE2658F6632C4E2B96B27C68E7421AFE",
                UUID("ee2658f6-632c-4e2b-96b2-7c68e7421afe"),
            ),
        ],
    )
    def test__cast(self, field_path, input, output) -> None:
        meta = FrozenObjectMeta(
            model="tests.FlatModel",
            fields={"test_field": field_path},
            frozen_at=None,
        )
        assert meta._cast("test_field", input) == output


@pytest.mark.django_db
class TestCreateMeta:
    """Group together create_meta function tests."""

    @pytest.mark.parametrize(
        "include,exclude,select_related,result",
        [
            ([], [], [], ["id", "frozen"]),
            (["id"], [], [], ["id"]),
            ([], ["id"], [], ["frozen"]),
            ([], ["id"], ["fresh"], ["frozen", "fresh"]),
            (["id"], [], ["fresh"], ["id", "fresh"]),
            ([], [], ["fresh"], ["id", "frozen", "fresh"]),
        ],
    )
    def test__gather_fields(
        self,
        include: AttributeList,
        exclude: AttributeList,
        select_related: AttributeList,
        result: AttributeList,
    ) -> None:
        fields = _gather_fields(NestedModel, include, exclude, select_related)
        assert [f.name for f in fields] == result

    @pytest.mark.django_db
    @pytest.mark.parametrize(
        "include,exclude,frozen_attrs",
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
            ),
            (
                ["field_int"],
                [],
                ["field_int"],
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
            ),
        ],
    )
    @freezegun.freeze_time(TEST_NOW)
    def test_create_meta(
        self,
        include: AttributeList,
        exclude: AttributeList,
        frozen_attrs: AttributeList,
    ) -> None:
        meta = create_meta(FlatModel, include=["field_int"])
        assert meta is not None
        assert meta.model == "tests.FlatModel"
        assert meta.fields == {"field_int": "django.db.models.fields.IntegerField"}
        assert meta.frozen_at == TEST_NOW

    def test_create_meta__value_error(self) -> None:
        with pytest.raises(ValueError):
            create_meta(int)
        with pytest.raises(ValueError):
            create_meta(FlatModel, include=["foo"], exclude=["bar"])


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

    def test_unfreeze_object(self) -> None:
        obj = unfreeze_object(TEST_DATA)
        assert obj is not None
        assert is_dataclass_instance(obj, "FrozenFlatModel")
        assert obj.id == 1
        assert obj.field_int == 999
        assert obj.field_str == "This is some text"
        assert obj.field_bool == True
        assert obj.field_date == date(2021, 6, 4)
        assert obj.field_datetime == datetime(
            2021, 6, 4, 18, 10, 30, 548000, tzinfo=pytz.UTC
        )
        assert obj.field_decimal == Decimal("3.142")
        assert obj.field_float == float(1)
        assert obj.field_uuid == UUID("6f09460c-c82b-4c8f-9d94-8828402da52e")
        assert obj.field_json == {"foo": "bar"}


@pytest.mark.django_db
def test_pickle_frozen_object(flat: FlatModel) -> None:
    frozen = freeze_object(flat)
    p = pickle.dumps(frozen)
    q = pickle.loads(p)
    assert q == frozen
