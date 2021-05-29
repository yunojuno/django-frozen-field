from __future__ import annotations


class FrozenObjectError(Exception):
    """Base class for package errors."""


class StaleObjectError(FrozenObjectError):
    """
    Custom error raised when a defrosted object is saved.

    If an object is deserialized it may be quite old, and out of
    sync with the original. If the deserialized object is then
    saved it will overwrite the existing (current) object, which
    is not the correct behaviour.

    """

    def __init__(self) -> None:
        super().__init__("Object was frozen; defrosted objects cannot be saved.")


class FrozenAttribute(FrozenObjectError):
    """Custom error raised when trying to edit a frozen value."""

    def __init__(self) -> None:
        super().__init__("Object was frozen; attributes cannot be changed.")


class ExcludedAttribute(FrozenObjectError):
    """Custom error raised when trying to get an attr that was excluded."""

    def __init__(self) -> None:
        super().__init__("Attribute was excluded from frozen object.")
