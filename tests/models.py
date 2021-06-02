from django.db import models

from frozen_field.fields import FrozenObjectField


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


class NestedModel(models.Model):
    frozen = FrozenObjectField(
        FlatModel,
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
        NestedModel,
        include=["id", "frozen"],
        null=True,
        blank=True,
    )
    fresh = models.ForeignKey(
        NestedModel,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
