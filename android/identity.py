from __future__ import annotations

from dataclasses import dataclass
from numbers import Integral
import re


_PACKAGE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)*$")
_CLASS_RE = re.compile(r"^\.?[A-Za-z_$][A-Za-z0-9_.$]*$")


def _normalize_required_text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} cannot be empty")
    return normalized


@dataclass(frozen=True, slots=True, order=True)
class AndroidUserId:
    """Concrete Android framework user identity."""

    value: int

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or not isinstance(self.value, Integral):
            raise TypeError("Android user id must be an integer")
        normalized = int(self.value)
        if normalized < 0:
            raise ValueError("Android user id cannot be negative")
        object.__setattr__(self, "value", normalized)

    def __int__(self) -> int:
        return self.value

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True, order=True)
class AndroidPackageName:
    """Android package name suitable for typed package-manager/activity commands."""

    value: str

    def __post_init__(self) -> None:
        normalized = _normalize_required_text(self.value, field_name="Android package name")
        if _PACKAGE_RE.fullmatch(normalized) is None:
            raise ValueError("Android package name has unsupported syntax")
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True, order=True)
class AndroidComponentName:
    """Android activity/service component expressed as package plus class name."""

    package: AndroidPackageName
    class_name: str

    def __post_init__(self) -> None:
        if not isinstance(self.package, AndroidPackageName):
            raise TypeError("Android component package must be AndroidPackageName")
        class_name = _normalize_required_text(
            self.class_name,
            field_name="Android component class name",
        )
        if _CLASS_RE.fullmatch(class_name) is None:
            raise ValueError("Android component class name has unsupported syntax")
        object.__setattr__(self, "class_name", class_name)

    @property
    def flattened(self) -> str:
        return f"{self.package.value}/{self.class_name}"

    def __str__(self) -> str:
        return self.flattened


__all__ = ["AndroidComponentName", "AndroidPackageName", "AndroidUserId"]
