import dataclasses
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import freezegun
import pytest
import pytz
from django.db.models.fields import (
    BooleanField,
    DateField,
    DateTimeField,
    DecimalField,
    Field,
    FloatField,
    IntegerField,
    TextField,
    UUIDField,
)
from django.db.models.fields.json import JSONField
from django.utils.timezone import now as tz_now

from frozen_field.models import FrozenObjectMeta, strip_meta
from frozen_field.types import AttributeList

TEST_NOW = tz_now()


@pytest.mark.django_db
class TestFrozenObjectMeta:
    @freezegun.freeze_time(TEST_NOW)
    def test_defaults(self) -> None:
        meta = FrozenObjectMeta(model="tests.FlatModel")
        assert meta.fields == {}
        assert meta.properties == []
        assert meta.frozen_at == TEST_NOW

    def test_cls_name(self) -> None:
        meta = FrozenObjectMeta(model="tests.FlatModel")
        assert meta.cls_name == "FrozenFlatModel"

    @pytest.mark.parametrize(
        "fields,properties,frozen_attrs",
        [
            ({}, [], []),
            ({"foo": 1}, [], ["foo"]),
            ({"foo": 1}, ["bar"], ["foo", "bar"]),
            ({}, ["bar"], ["bar"]),
            ({"foo": 1, "bar": False}, [], ["foo", "bar"]),
        ],
    )
    def test_frozen_attrs(
        self, fields: dict, properties: AttributeList, frozen_attrs: AttributeList
    ) -> None:
        meta = FrozenObjectMeta("tests.FlatModel", fields, properties)
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
            [],
            frozen_at=tz_now(),
        )
        klass = meta.make_dataclass()
        assert [f.name for f in dataclasses.fields(klass)] == ["meta", "field_int"]
        obj1 = klass(meta, 999)
        assert obj1.json_data() == {"field_int": 999}
        assert obj1.__module__ == "frozen_field.models"
        with pytest.raises(dataclasses.FrozenInstanceError):
            obj1.field_int = 0

        obj2 = klass(meta, 999)
        assert obj1 == obj2
        obj3 = klass(meta, 998)
        assert obj1 != obj3

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
    def test__field(self, field_path: str, field_klass: Field) -> None:
        meta = FrozenObjectMeta(
            model="tests.FlatModel",
            fields={"test_field": field_path},
            frozen_at=TEST_NOW,
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
    def test_to_python_fields(
        self, field_path: str, input: str, output: object
    ) -> None:
        meta = FrozenObjectMeta(
            model="tests.FlatModel",
            fields={"test_field": field_path},
            frozen_at=TEST_NOW,
        )
        assert meta.to_python("test_field", input) == output

    @pytest.mark.parametrize(
        "input,output",
        [
            (1, 1),
            ("1", "1"),
        ],
    )
    def test_to_python__properties(self, input: str, output: object) -> None:
        meta = FrozenObjectMeta(model="tests.FlatModel", properties=["test_property"])
        assert meta.to_python("test_property", input) == output


@pytest.mark.django_db
def test_strip_meta(deep: dict) -> None:
    deep = {
        "meta": {
            "model": "tests.NestedModel",
            "fields": {
                "id": "django.db.models.fields.AutoField",
                "frozen": "frozen_field.fields.FrozenObjectField",
                "fresh": "django.db.models.fields.related.ForeignKey",
            },
            "properties": [],
            "frozen_at": "2021-06-06T13:26:03.655Z",
        },
        "id": 1,
        "frozen": {
            "meta": {
                "model": "tests.FlatModel",
                "fields": {
                    "id": "django.db.models.fields.AutoField",
                },
                "properties": [],
                "frozen_at": "2021-06-06T13:26:03.655Z",
            },
            "id": 1,
        },
        "fresh": {
            "meta": {
                "model": "tests.FlatModel",
                "fields": {
                    "id": "django.db.models.fields.AutoField",
                },
                "properties": [],
                "frozen_at": "2021-06-06T13:26:03.656Z",
            },
            "id": 1,
        },
    }
    assert strip_meta(deep) == {"id": 1, "frozen": {"id": 1}, "fresh": {"id": 1}}
