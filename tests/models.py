from django.db import models
from django.db.models.fields.related import ForeignKey

from frozen_data.fields import FrozenDataField
from frozen_data.mixins import FrozenDataMixin


class FlatModel(FrozenDataMixin, models.Model):
    field_int = models.IntegerField()
    field_str = models.TextField()
    field_bool = models.BooleanField()
    field_date = models.DateField()
    field_decimal = models.DecimalField(decimal_places=3, max_digits=8)
    field_datetime = models.DateTimeField()
    field_uuid = models.UUIDField()

class NestedModel(FrozenDataMixin, models.Model):
    frozen = FrozenDataField(FlatModel)
    current = ForeignKey(FlatModel, on_delete=models.CASCADE)



