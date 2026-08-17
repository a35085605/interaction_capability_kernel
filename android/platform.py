from __future__ import annotations

from dataclasses import dataclass
from numbers import Integral


def _normalize_positive_integer(value: object, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError(f"{field_name} must be an integer")
    normalized = int(value)
    if normalized <= 0:
        raise ValueError(f"{field_name} must be greater than zero")
    return normalized


def _normalize_required_text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} cannot be empty")
    return normalized


@dataclass(frozen=True, slots=True)
class AndroidBuildInfo:
    """Small set of Android build facts used for compatibility decisions.

    This intentionally does not aggregate command/backend capability policy. A caller may use
    these facts together with independently observed ADB transport features or mechanism-specific
    evidence when selecting an adapter/parser strategy.
    """

    sdk_int: int
    release: str
    fingerprint: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "sdk_int",
            _normalize_positive_integer(self.sdk_int, field_name="Android SDK level"),
        )
        object.__setattr__(
            self,
            "release",
            _normalize_required_text(self.release, field_name="Android release"),
        )
        object.__setattr__(
            self,
            "fingerprint",
            _normalize_required_text(self.fingerprint, field_name="Android build fingerprint"),
        )


__all__ = ["AndroidBuildInfo"]
