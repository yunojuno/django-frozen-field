from django.db import models

from frozen_field.fields import FrozenObjectField


class Address(models.Model):

    line1 = models.CharField(max_length=100, blank=True)
    line2 = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    region = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)


class Order(models.Model):
    billing_address = models.ForeignKey(Address, on_delete=models.CASCADE)
    delivery_address = FrozenObjectField(Address, blank=True, null=True)
