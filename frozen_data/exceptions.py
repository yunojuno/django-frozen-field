from __future__ import annotations


class FrozenObjectError(Exception):
    """Base class for package errors."""


class FrozenAttributeError(FrozenObjectError):
    """Custom error raised when trying to edit a frozen value."""

    def __init__(self) -> None:
        super().__init__("Frozen attributes cannot be changed.")


class MissingAttributeError(FrozenObjectError):
    """Custom error raised when trying to get an attr that was excluded."""

    def __init__(self, attr_name: str) -> None:
        super().__init__(f"Attribute '{attr_name}' was excluded from frozen object.")
