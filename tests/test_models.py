import dataclasses
import json
import pickle

import pytest
from django.core.serializers.json import DjangoJSONEncoder

from frozen_field.models import create_meta, freeze_object, unfreeze_object
from tests.models import NestedModel
from tests.test_fields import _flat, nested

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
    def test_create_meta(self, flat, include, exclude, frozen_attrs):
        meta = create_meta(flat, include=include, exclude=exclude)
        assert meta.frozen_attrs == frozen_attrs

    def test_extract_model_values__error(self, flat):
        nested = NestedModel()
        meta = create_meta(flat)
        with pytest.raises(ValueError):
            _ = meta.extract_model_values(nested)


@pytest.mark.django_db
def test_create_frozen_object(flat):
    # flat = _flat()
    frozen_obj = freeze_object(flat)
    for f in frozen_obj.meta.frozen_attrs:
        assert getattr(flat, f) == getattr(frozen_obj, f)
    for f in frozen_obj.meta.frozen_attrs:
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(frozen_obj, f, getattr(flat, f))


@pytest.mark.django_db
def test_dump_frozen_object(flat):
    flat.refresh_from_db()
    nested_obj = NestedModel(fresh=flat, frozen=flat)
    nested_obj.save()
    frozen_obj = freeze_object(nested_obj, include=["frozen", "fresh"])
    as_dict = dataclasses.asdict(frozen_obj)


@pytest.mark.django_db
def test_load_frozen_object(flat):
    nested_obj = NestedModel(fresh=flat, frozen=flat)
    nested_obj.save()
    frozen_obj = freeze_object(nested_obj, include=["frozen", "fresh"])
    as_dict = dataclasses.asdict(frozen_obj)
    raw = json.dumps(as_dict, cls=DjangoJSONEncoder)
    refreshed = unfreeze_object(as_dict)


@pytest.mark.django_db
def test_pickle_frozen_object(flat):
    frozen = freeze_object(flat)
    p = pickle.dumps(frozen)
    q = pickle.loads(p)
    assert q == frozen
