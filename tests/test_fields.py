from typing import Optional, Union
from unittest import mock

import pytest
from django.core.exceptions import ValidationError
from django.db.models.base import Model

from frozen_field.fields import FrozenObjectField
from frozen_field.models import FrozenObjectMeta
from frozen_field.types import FrozenModel, is_dataclass_instance
from tests.test_models import TEST_NOW

from .models import DeepNestedModel, FlatModel, NestedModel


@pytest.mark.django_db
class TestFrozenObjectField:
    @pytest.mark.parametrize("source_model", ["tests.FlatModel", FlatModel])
    def test_initialisation(self, source_model: Union[str, Model]) -> None:
        field = FrozenObjectField(source_model)
        assert field.source_model == source_model
        assert field.include == []
        assert field.exclude == []
        assert field.select_related == []

    @pytest.mark.parametrize("source_model", ["tests.FlatModel", FlatModel])
    def test__source_model_klass(self, source_model: Union[str, Model]) -> None:
        field = FrozenObjectField(source_model)
        assert field._source_model_klass == FlatModel

    @pytest.mark.parametrize("source_model", [None, 1, True])
    def test__source_model_klass__value_error(
        self, source_model: Union[str, Model]
    ) -> None:
        field = FrozenObjectField(source_model)
        with pytest.raises(ValueError):
            _ = field._source_model_klass

    def test_validate_model(self) -> None:
        field = FrozenObjectField(FlatModel)
        obj = NestedModel()
        with pytest.raises(ValidationError):
            field.validate_model(obj)

    @mock.patch("frozen_field.fields.unfreeze_object")
    def test_from_db_value(self, mock_unfreeze: mock.Mock, flat: FlatModel) -> None:
        field = FrozenObjectField(FlatModel)
        assert (
            field.from_db_value('{"meta": {}}', None, None)
            == mock_unfreeze.return_value
        )

    @pytest.mark.parametrize(
        "value,result",
        [
            (None, None),
            (
                FrozenObjectMeta("tests.FlatModel", {}, "2021-06-04T18:10:30.549Z"),
                '{"model": "tests.FlatModel", "fields": {}, "frozen_at": "2021-06-04T18:10:30.549Z"}',
            ),
        ],
    )
    def test_get_prep_value(
        self, value: Optional[FrozenModel], result: Optional[dict]
    ) -> None:
        field = FrozenObjectField(FlatModel)
        assert field.get_prep_value(value) == result

    @pytest.mark.parametrize(
        "value,result",
        [
            (None, None),
            ("", None),
            ("{}", None),
        ],
    )
    def test_from_db_value__empty(
        self, value: Optional[str], result: Optional[FrozenModel]
    ) -> None:
        field = FrozenObjectField(FlatModel)
        assert field.from_db_value(value, None, None) == result


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
        assert isinstance(nested.frozen, FlatModel)
        nested.refresh_from_db()
        assert isinstance(nested.fresh, FlatModel)
        # frozen field has been serialized and is now a FrozenObject
        assert is_dataclass_instance(nested.frozen, "FrozenFlatModel")

    def test_deep_nested(self, nested: NestedModel) -> None:
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
