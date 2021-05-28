from __future__ import annotations


class StaleObjectError(Exception):
    """
    Custom error raised when a defrosted object is saved.

    If an object is deserialized it may be quite old, and out of
    sync with the original. If the deserialized object is then
    saved it will overwrite the existing (current) object, which
    is not the correct behaviour.

    """

    def __init__(self) -> None:
        super().__init__("Object was frozen; defrosted objects cannot be saved.")


class FrozenAttribute(Exception):
    """Custom error raised when trying to edit a frozen value."""

    def __init__(self) -> None:
        super().__init__("Object was frozen; attributes cannot be changed.")
