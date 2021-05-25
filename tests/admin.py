from django.contrib import admin

from .models import FlatModel, NestedModel


@admin.register(FlatModel)
class FlatModelAdmin(admin.ModelAdmin):
    pass


@admin.register(NestedModel)
class NestedModelAdmin(admin.ModelAdmin):
    pass
