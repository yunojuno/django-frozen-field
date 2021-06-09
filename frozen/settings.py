from typing import Callable

from django.conf import settings
from django.db.models.fields import Field

# map of field_klass:func used to override default behaviour, which is
# to load the field class and call the to_python method. e.g.
FIELD_CONVERTERS: dict[Field, Callable[[object], object]] = getattr(
    settings, "frozen_CONVERTERS", {}
)
