from django.core.serializers.json import DjangoJSONEncoder
from django.db import models

from frozen_field.fields import FrozenObjectField


class CustomJSONEncoder(DjangoJSONEncoder):
    """Custom encoder used to test field deconstruct method."""


class FlatModel(models.Model):

    field_int = models.IntegerField()
    field_str = models.TextField()
    field_bool = models.BooleanField()
    field_date = models.DateField()
    field_datetime = models.DateTimeField()
    field_decimal = models.DecimalField(decimal_places=3, max_digits=8)
    field_float = models.FloatField()
    field_uuid = models.UUIDField()
    field_json = models.JSONField(null=True)

    @property
    def is_bool(self) -> bool:
        """Test model property."""
        return True


class NestedModel(models.Model):
    frozen = FrozenObjectField(
        FlatModel,
        select_properties=["is_bool"],
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
    fresh = models.ForeignKey(
        NestedModel,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
