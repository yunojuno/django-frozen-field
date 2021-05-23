from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from typing import Optional, cast

from django.core import serializers
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db.models.fields.related import ForeignKey, OneToOneField
from django.utils.timezone import now as tz_now

from frozen_data.fields import FrozenDataField

from .exceptions import StaleObjectError


class FrozenDataMixin:
    """
    Mixin for classes that support freezing.

    Freezable objects are those that can be serialized and
    stored in a JSONField and then deserialized back into
    an equivalent object.

        >>> assert Klass.deserialize(**obj.serialize()) == obj

    The gotcha in this process is that if an object is frozen
    and later deserialized it will be out of sync with the original
    object, and there is a danger that if the calling code then
    calls `save` (or causes it to be called inadvertently) that
    the old frozen details will overwrite more recent edits.

    This mixin prevents that by adding a `_raw` property to the
    deserialized instance that contains the data from which the object
    was instantiated. If this field exists, attempting to save the
    object will raise StaleObjectError.

    This error should never appear in the wild - it's there as a
    warning in case people are using deserialized frozen data (which
    should only be used in a read-only manner) incorrectly.

    This mixin implements the serialize and deserialize methods.

    """

    # stops mypy complaining
    _meta: models.options.Options

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)  # type: ignore
        self.frozen_at: Optional[datetime] = None
        self._id: Optional[int] = None
        self._raw: Optional[dict] = None

    @classmethod
    def _fields(cls, action: str) -> list[str]:
        """
        Split fields according to how they should be serialized.

        When fields are serialized they can be treated in one of three
        ways - copied directly (by value), referenced by id, or frozen.

        """
        if action not in ["copy", "serialize", "lazy"]:
            raise ValueError("Invalid action value.")
        data = defaultdict(list)
        for f in cls._meta.get_fields():
            if isinstance(f, FrozenDataField):
                data["serialize"].append(f.name)
            elif isinstance(f, (ForeignKey, OneToOneField)):
                data["lazy"].append(f"{f.name}_id")
            else:
                data["copy"].append(f.name)
        return data[action]

    def _serialize(self) -> dict:
        """
        Convert obj to a dict using standard Django Serializer.

        This method excludes fields that have a related model in the initial
        serialization - these are patched in after using the lazy eval version
        of the field - so `freelancer` becomes `freelancer_id`.

        """
        # serialize method requires an iterable, so we pass in a list of one
        output = serializers.serialize(
            "json",
            [self],
            cls=DjangoJSONEncoder,
            fields=self._fields("copy"),
        )
        # parse the output (str) to extract the object itself
        data = json.loads(output)[0]["fields"]
        # add in the lazy-loaded fields
        for f in self._fields("lazy"):
            data[f] = getattr(self, f)
        # id is not included in the default output
        data["_id"] = self.id  # type: ignore
        data["frozen_at"] = tz_now().isoformat()
        return data

    def freeze(self) -> dict:
        """
        Perform recursive deep serialize of object and all FKs.

        The serialization of objects is a three-part process that starts with
        the default Django JSON serializer. With this as the baseline we then
        ensure that all related fields that refer to a FrozenDataMixin model are
        themselves serialized (this is recursive), and fix the non-frozen
        related fields to refer to the lazy `{name}_id` field so that the models
        deserialize correctly.

        The key issue with the default serialization is that FKs are not
        "frozen" - the object retains a reference to the FK, but it loses the
        snapshot of values.

        Taking a model that has the following fields (pseudocode):

            class X(Model):
                foo = IntegerField()
                bar = ForeignKey(Model subclass)
                baz = ForeignKey(FrozeDataMixin subclass)

        This would serialize by default as:

            {
                "foo": 123,  # just a straight value (int, str, bool, etc.)
                "bar": 456,  # FK to non-freezable object
                "baz": 789,  # FK to a FrozenDataModel object
            }

        If we were to deserialize this we would references to the current versions
        of the bar and baz objects - and _not_ the frozen versions.

        We convert this to:

            {
                "foo": 123,      # unchanged
                "bar_id": 456,   # key is updated
                "baz": { ... },  # object is serialized
            }

        If we deserialize this we get the baz object as it was at the time of
        serialization.

        """
        data = self._serialize()
        for f in self._fields("serialize"):
            data[f] = getattr(self, f).freeze()
        return data

    @classmethod
    def unfreeze(cls, **kwargs: object) -> FrozenDataMixin:
        """Deserialize dict back into object representation."""
        instance = cls()
        for k, v in kwargs.items():
            if k in (cls._fields("copy") + cls._fields("lazy")):
                setattr(instance, k, v)
            if k in cls._fields("serialize"):
                klass = cls._meta.get_field(k).app_model
                setattr(instance, k, klass.unfreeze(**v))
        instance.frozen_at = cast(datetime, kwargs.pop("frozen_at"))
        instance._id = cast(int, kwargs.pop("_id"))
        instance._raw = kwargs
        return instance

    def save(self, *args: object, **kwargs: object) -> object | None:
        if self.frozen_at:
            raise StaleObjectError(self)
        return super().save(*args, **kwargs)  # type: ignore
