from django.db import models
from django.db.models.fields import BLANK_CHOICE_DASH
from django.db.models.fields.related import ForeignKey

from frozen_data.fields import FrozenDataField


class FlatModel(models.Model):
    field_int = models.IntegerField()
    field_str = models.TextField()
    field_bool = models.BooleanField()
    field_date = models.DateField()
    field_decimal = models.DecimalField(decimal_places=3, max_digits=8)
    field_datetime = models.DateTimeField()
    field_float = models.FloatField()
    field_uuid = models.UUIDField()


class NestedModel(models.Model):
    frozen = FrozenDataField(FlatModel, null=True, blank=True)
    current = ForeignKey(FlatModel, on_delete=models.CASCADE, null=True, blank=True)
