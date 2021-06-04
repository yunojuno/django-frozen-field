import datetime

import pytest
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models.fields import DateTimeField

from frozen_field.types import is_dataclass_instance

from .models import DeepNestedModel, FlatModel, NestedModel


def truncate_datetime(dt: datetime.datetime) -> datetime.datetime:
    """Truncate microseconds to milliseconds."""
    encoder = DjangoJSONEncoder()
    field = DateTimeField()
    return field.to_python(encoder.default(dt))


@pytest.mark.django_db
class TestFrozenObjectField:
    def test_serialization(self, flat: FlatModel) -> None:
        nested = NestedModel.objects.create(frozen=flat, fresh=flat)
        nested.refresh_from_db()
        for f in FlatModel._meta.local_fields:
            fresh_value = getattr(nested.fresh, f.name)
            frozen_value = getattr(nested.frozen, f.name)
            # see notes in README on datetime truncation
            if isinstance(f, DateTimeField):
                fresh_value = truncate_datetime(fresh_value)
            assert frozen_value == fresh_value

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
