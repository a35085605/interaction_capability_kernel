from __future__ import annotations

from dataclasses import dataclass


def _normalize_required_text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} cannot be empty")
    return normalized


@dataclass(frozen=True, slots=True, order=True)
class CaptureSourceId:
    """Opaque identity of the native source selected by a capture backend.

    The capture domain does not interpret the value. Platform adapters may expose a separate
    typed descriptor that maps this opaque source identity to platform-native source facts.
    """

    value: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "value",
            _normalize_required_text(self.value, field_name="capture source id"),
        )

    def __str__(self) -> str:
        return self.value


__all__ = ["CaptureSourceId"]
