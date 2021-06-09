from __future__ import annotations

from typing import Optional, Union
from unittest import mock

import pytest
from django.db.models import Model, fields

from frozen_field.fields import FrozenObjectDescriptor, FrozenObjectField
from frozen_field.models import FrozenObjectMeta
from frozen_field.serializers import freeze_object
from frozen_field.types import (
    AttributeList,
    AttributeName,
    FrozenModel,
    is_dataclass_instance,
)

from .models import FlatModel


class DescriptorAccess:
    """Use to assert access via descriptor."""

    def assert_field_value(self, name: AttributeName, value: object) -> None:
        assert self.__dict__[name] == value


@pytest.mark.django_db
class TestFrozenObjectDescriptor:
    def _descriptor(self, field: fields.Field) -> FrozenObjectDescriptor:
        return FrozenObjectDescriptor(field)

    def _field(
        self,
        model: Model,
        include: AttributeList | None = None,
        exclude: AttributeList | None = None,
        select_related: AttributeList | None = None,
        select_properties: AttributeList | None = None,
    ) -> FrozenObjectField:
        field = FrozenObjectField(
            model, include, exclude, select_related, select_properties
        )
        field.name = "test_field"
        return field

    def test__set__none(self, flat: FlatModel) -> None:
        field = self._field(FlatModel, [], [], [], [])
        descriptor = self._descriptor(field)
        obj = DescriptorAccess()
        descriptor.__set__(obj, None)
        assert obj.__dict__[field.name] is None

    def test__set__model(self, flat: FlatModel) -> None:
        field = self._field(FlatModel, [], [], [], [])
        descriptor = self._descriptor(field)
        obj = DescriptorAccess()
        descriptor.__set__(obj, flat)
        assert is_dataclass_instance(
            obj.__dict__[field.name], cls_name="FrozenFlatModel"
        )

    def test__set__dataclass(self, flat: FlatModel) -> None:
        field = self._field(FlatModel, [], [], [], [])
        descriptor = self._descriptor(field)
        instance = DescriptorAccess()
        value = freeze_object(flat)
        assert is_dataclass_instance(value, cls_name="FrozenFlatModel")
        descriptor.__set__(instance, value)
        assert is_dataclass_instance(
            instance.__dict__[field.name], cls_name="FrozenFlatModel"
        )

    def test__set__dict(self, flat: FlatModel) -> None:
        field = self._field(FlatModel, [], [], [], [])
        descriptor = self._descriptor(field)
        instance = DescriptorAccess()
        value = freeze_object(flat).json_data()  # type: ignore [union-attr]
        with pytest.raises(ValueError):
            descriptor.__set__(instance, value)


@pytest.mark.django_db
class TestFrozenObjectField:
    @pytest.mark.parametrize("model", ["tests.FlatModel", FlatModel])
    def test_initialisation(self, model: Union[str, Model]) -> None:
        field = FrozenObjectField(model)
        assert field.model_klass == FlatModel
        assert field.model_name == "FlatModel"
        assert field.model_label == "tests.FlatModel"
        assert field.include == []
        assert field.exclude == []
        assert field.select_related == []
        assert field.select_properties == []

    @pytest.mark.parametrize("model", [None, 1, True])
    def test_initialisation__value_error(self, model: Union[str, Model]) -> None:
        with pytest.raises(ValueError):
            _ = FrozenObjectField(model)

    @pytest.mark.parametrize("model", ["tests.FlatModel", FlatModel])
    def test_model_klass(self, model: Union[str, Model]) -> None:
        field = FrozenObjectField(model)
        assert field.model_klass == FlatModel

    @mock.patch("frozen_field.fields.unfreeze_object")
    def test_from_db_value(self, mock_unfreeze: mock.Mock, flat: FlatModel) -> None:
        field = FrozenObjectField(FlatModel)
        assert (
            field.from_db_value('{"_meta": {}}', None, None)
            == mock_unfreeze.return_value
        )

    @pytest.mark.parametrize(
        "value,result",
        [
            (None, None),
            (
                FrozenObjectMeta("tests.FlatModel", {}, [], "2021-06-04T18:10:30.549Z"),
                (
                    '{"model": "tests.FlatModel", "fields": {}, "properties": [], '
                    '"frozen_at": "2021-06-04T18:10:30.549Z"}'
                ),
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
