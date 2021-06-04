import dataclasses
import json
import pickle

import pytest
from django.core.serializers.json import DjangoJSONEncoder

from frozen_field.models import create_meta, freeze_object, unfreeze_object
from frozen_field.types import AttributeList
from tests.models import FlatModel, NestedModel

TEST_DATA = {
    "meta": {
        "model": "Address",
        "frozen_at": "2021-05-28T16:42:43.829687+00:00",
        "fields": {
            "id": "django.db.models.IntegerField",
            "line_1": "django.db.models.CharField",
            "line_2": "django.db.models.CharField",
        },
    },
    "id": 1,
    "line_1": "29 Acacia Avenue",
    "line_2": "Nuttytown",
}


@pytest.mark.django_db
class TestFrozenObjectMeta:
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
    def test_create_meta(
        self,
        flat: FlatModel,
        include: AttributeList,
        exclude: AttributeList,
        frozen_attrs: AttributeList,
    ) -> None:
        meta = create_meta(flat, include=include, exclude=exclude)
        assert meta and meta.frozen_attrs == frozen_attrs

    def test_parse_obj__error(self, flat: FlatModel) -> None:
        nested = NestedModel()
        meta = create_meta(flat)
        assert meta
        with pytest.raises(ValueError):
            _ = meta.parse_obj(nested)


@pytest.mark.django_db
def test_create_frozen_object(flat: FlatModel) -> None:
    frozen_obj = freeze_object(flat)
    assert frozen_obj
    for f in frozen_obj.meta.frozen_attrs:  # type:ignore [attr-defined]
        assert getattr(flat, f) == getattr(frozen_obj, f)
    for f in frozen_obj.meta.frozen_attrs:  # type:ignore [attr-defined]
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(frozen_obj, f, getattr(flat, f))


@pytest.mark.django_db
def test_dump_frozen_object(flat: FlatModel) -> None:
    flat.refresh_from_db()
    nested_obj = NestedModel(fresh=flat, frozen=flat)
    nested_obj.save()
    frozen_obj = freeze_object(nested_obj, include=["frozen", "fresh"])
    as_dict = dataclasses.asdict(frozen_obj)


@pytest.mark.django_db
def test_load_frozen_object(flat: FlatModel) -> None:
    nested_obj = NestedModel(fresh=flat, frozen=flat)
    nested_obj.save()
    frozen_obj = freeze_object(nested_obj, include=["frozen", "fresh"])
    as_dict = dataclasses.asdict(frozen_obj)
    raw = json.dumps(as_dict, cls=DjangoJSONEncoder)
    refreshed = unfreeze_object(as_dict)


@pytest.mark.django_db
def test_pickle_frozen_object(flat: FlatModel) -> None:
    frozen = freeze_object(flat)
    p = pickle.dumps(frozen)
    q = pickle.loads(p)
    assert q == frozen
