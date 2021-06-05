from typing import Optional, Union
from unittest import mock

import pytest
from django.db.models.base import Model

from frozen_field.fields import FrozenObjectField
from frozen_field.models import FrozenObjectMeta
from frozen_field.types import FrozenModel

from .models import FlatModel


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
            field.from_db_value('{"meta": {}}', None, None)
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
