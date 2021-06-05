from __future__ import annotations

import pytest

from frozen_field.serializers import strip_dict, strip_list
from frozen_field.types import AttributeList, AttributeName, is_dataclass_instance

from .models import DeepNestedModel, FlatModel, NestedModel


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


@pytest.mark.parametrize(
    "input,field_name,output",
    [
        ([""], "foo", []),
        (["foo"], "foo", []),
        (["foo__bar"], "foo", ["bar"]),
        (["foo__bar__baz"], "foo", ["bar__baz"]),
        (["bar__foo__baz"], "foo", []),
        (["foo", "foo__bar", "foo__bar__baz"], "foo", ["bar", "bar__baz"]),
    ],
)
def test_strip_list(
    input: AttributeList, field_name: AttributeName, output: AttributeList
) -> None:
    assert strip_list(input, field_name) == output


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
