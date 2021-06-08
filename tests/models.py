import uuid
from datetime import date, datetime

from django.core.serializers.json import DjangoJSONEncoder
from django.db import models

from frozen_field.fields import FrozenObjectField


class CustomJSONEncoder(DjangoJSONEncoder):
    """Custom encoder used to test field deconstruct method."""


def to_date(value: str) -> date:
    """Test field converter."""
    return datetime.strptime(value, "%Y-%m-%d").date()


class FlatModel(models.Model):

    field_int = models.IntegerField(default=999)
    field_str = models.TextField(default="Hello, world!")
    field_bool = models.BooleanField(default=False)
    field_date = models.DateField(auto_now_add=True)
    field_datetime = models.DateTimeField(auto_now_add=True)
    field_decimal = models.DecimalField(default="3.14", decimal_places=3, max_digits=8)
    field_float = models.FloatField(default=float("3.14"))
    field_uuid = models.UUIDField(default=uuid.uuid4)
    field_json = models.JSONField(null=True)

    @property
    def is_bool(self) -> bool:
        """Test model property."""
        return True

    @property
    def today(self) -> date:
        """Test model property."""
        return date.today()


class NestedModel(models.Model):
    frozen = FrozenObjectField(
        FlatModel,
        select_properties=["is_bool", "today"],
        converters={"today": to_date},
        null=True,
        blank=True,
    )
    fresh = models.ForeignKey(
        FlatModel,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )


class DeepNestedModel(models.Model):
    frozen = FrozenObjectField(
        "tests.NestedModel",
        encoder=CustomJSONEncoder,
        include=["id", "frozen"],
        select_related=["fresh"],
        null=True,
        blank=True,
    )
    partial = FrozenObjectField(
        "tests.NestedModel",
        encoder=CustomJSONEncoder,
        include=["fresh__field_int"],
        select_properties=["fresh__today"],
        null=True,
        blank=True,
    )
    fresh = models.ForeignKey(
        NestedModel,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
