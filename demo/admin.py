from django.contrib import admin

from demo.models import Address, Order


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    pass


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    raw_id_fields = ("billing_address",)
    readonly_fields = ("delivery_address",)
