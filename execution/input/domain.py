from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from numbers import Integral
from typing import Generic, TypeVar


PointT = TypeVar("PointT")


def _normalize_integer(value: object, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError(
            f"{field_name} must be an integer, got {type(value).__name__}"
        )
    return int(value)


def _normalize_positive_integer(value: object, *, field_name: str) -> int:
    normalized = _normalize_integer(value, field_name=field_name)
    if normalized <= 0:
        raise ValueError(f"{field_name} must be greater than zero")
    return normalized


def _normalize_non_empty_text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(
            f"{field_name} must be a string, got {type(value).__name__}"
        )
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} cannot be empty")
    return normalized


def _normalize_non_negative_duration(
    value: object,
    *,
    field_name: str,
) -> timedelta:
    if not isinstance(value, timedelta):
        raise TypeError(f"{field_name} must be timedelta")
    if value < timedelta(0):
        raise ValueError(f"{field_name} cannot be negative")
    return value


@dataclass(frozen=True, slots=True)
class ScrollDelta:
    """Semantic scroll steps, independent of backend-native units."""

    horizontal_steps: int = 0
    vertical_steps: int = 0

    def __post_init__(self) -> None:
        horizontal = _normalize_integer(
            self.horizontal_steps,
            field_name="horizontal scroll steps",
        )
        vertical = _normalize_integer(
            self.vertical_steps,
            field_name="vertical scroll steps",
        )
        if horizontal == 0 and vertical == 0:
            raise ValueError("scroll delta must contain at least one step")
        object.__setattr__(self, "horizontal_steps", horizontal)
        object.__setattr__(self, "vertical_steps", vertical)


class PointerButton(str, Enum):
    LEFT = "left"
    RIGHT = "right"
    MIDDLE = "middle"


@dataclass(frozen=True, slots=True)
class PointerMove(Generic[PointT]):
    point: PointT
    duration: timedelta = timedelta(0)

    def __post_init__(self) -> None:
        if self.point is None:
            raise TypeError("pointer move point cannot be None")
        object.__setattr__(
            self,
            "duration",
            _normalize_non_negative_duration(
                self.duration,
                field_name="pointer move duration",
            ),
        )


@dataclass(frozen=True, slots=True)
class PointerClick(Generic[PointT]):
    point: PointT
    button: PointerButton = PointerButton.LEFT
    count: int = 1
    interval: timedelta = timedelta(0)

    def __post_init__(self) -> None:
        if self.point is None:
            raise TypeError("pointer click point cannot be None")
        if not isinstance(self.button, PointerButton):
            raise TypeError("pointer click button must be PointerButton")
        object.__setattr__(
            self,
            "count",
            _normalize_positive_integer(
                self.count,
                field_name="pointer click count",
            ),
        )
        object.__setattr__(
            self,
            "interval",
            _normalize_non_negative_duration(
                self.interval,
                field_name="pointer click interval",
            ),
        )


@dataclass(frozen=True, slots=True)
class PointerScroll(Generic[PointT]):
    delta: ScrollDelta
    origin: PointT | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.delta, ScrollDelta):
            raise TypeError("pointer scroll delta must be ScrollDelta")


@dataclass(frozen=True, slots=True)
class PointerDrag(Generic[PointT]):
    start: PointT
    end: PointT
    button: PointerButton = PointerButton.LEFT
    duration: timedelta = timedelta(0)

    def __post_init__(self) -> None:
        if self.start is None or self.end is None:
            raise TypeError("pointer drag points cannot be None")
        if not isinstance(self.button, PointerButton):
            raise TypeError("pointer drag button must be PointerButton")
        object.__setattr__(
            self,
            "duration",
            _normalize_non_negative_duration(
                self.duration,
                field_name="pointer drag duration",
            ),
        )


@dataclass(frozen=True, slots=True, order=True)
class Key:
    """Backend-independent identity for a physical or logical key."""

    value: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "value",
            _normalize_non_empty_text(self.value, field_name="key"),
        )

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class KeyDown:
    key: Key

    def __post_init__(self) -> None:
        if not isinstance(self.key, Key):
            raise TypeError("key_down key must be Key")


@dataclass(frozen=True, slots=True)
class KeyUp:
    key: Key

    def __post_init__(self) -> None:
        if not isinstance(self.key, Key):
            raise TypeError("key_up key must be Key")


@dataclass(frozen=True, slots=True)
class KeyPress:
    key: Key
    repeat: int = 1
    interval: timedelta = timedelta(0)

    def __post_init__(self) -> None:
        if not isinstance(self.key, Key):
            raise TypeError("key press key must be Key")
        object.__setattr__(
            self,
            "repeat",
            _normalize_positive_integer(
                self.repeat,
                field_name="key press repeat",
            ),
        )
        object.__setattr__(
            self,
            "interval",
            _normalize_non_negative_duration(
                self.interval,
                field_name="key press interval",
            ),
        )


@dataclass(frozen=True, slots=True)
class KeyChord:
    keys: tuple[Key, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.keys, tuple):
            raise TypeError("key chord keys must be a tuple")
        if len(self.keys) < 2:
            raise ValueError("key chord requires at least two keys")
        for index, key in enumerate(self.keys):
            if not isinstance(key, Key):
                raise TypeError(f"key chord keys[{index}] must be Key")
        if len(set(self.keys)) != len(self.keys):
            raise ValueError("key chord cannot contain duplicate keys")


@dataclass(frozen=True, slots=True)
class TextEntry:
    text: str

    def __post_init__(self) -> None:
        if not isinstance(self.text, str):
            raise TypeError("text entry must be a string")
        if not self.text:
            raise ValueError("text entry cannot be empty")
