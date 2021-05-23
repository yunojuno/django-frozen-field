from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .mixins import FrozenDataMixin


class StaleObjectError(Exception):
    """
    Custom error raised when a defrosted object is saved.

    If an object is deserialized it may be quite old, and out of
    sync with the original. If the deserialized object is then
    saved it will overwrite the existing (current) object, which
    is not the correct behaviour.

    """

    def __init__(self, obj: FrozenDataMixin) -> None:
        super().__init__(
            f"Object was frozen at {obj.frozen_at}; defrosted objects cannot be saved."
        )
