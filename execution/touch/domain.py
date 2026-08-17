from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Generic, TypeVar


PointT = TypeVar("PointT")


def _normalize_positive_duration(value: object, *, field_name: str) -> timedelta:
    if not isinstance(value, timedelta):
        raise TypeError(f"{field_name} must be timedelta")
    if value <= timedelta(0):
        raise ValueError(f"{field_name} must be greater than zero")
    return value


@dataclass(frozen=True, slots=True)
class TouchTap(Generic[PointT]):
    point: PointT

    def __post_init__(self) -> None:
        if self.point is None:
            raise TypeError("touch tap point cannot be None")


@dataclass(frozen=True, slots=True)
class TouchLongPress(Generic[PointT]):
    point: PointT
    duration: timedelta = timedelta(milliseconds=500)

    def __post_init__(self) -> None:
        if self.point is None:
            raise TypeError("touch long-press point cannot be None")
        object.__setattr__(
            self,
            "duration",
            _normalize_positive_duration(self.duration, field_name="touch long-press duration"),
        )


@dataclass(frozen=True, slots=True)
class TouchSwipe(Generic[PointT]):
    start: PointT
    end: PointT
    duration: timedelta = timedelta(milliseconds=300)

    def __post_init__(self) -> None:
        if self.start is None or self.end is None:
            raise TypeError("touch swipe points cannot be None")
        object.__setattr__(
            self,
            "duration",
            _normalize_positive_duration(self.duration, field_name="touch swipe duration"),
        )


@dataclass(frozen=True, slots=True)
class TouchDragAndDrop(Generic[PointT]):
    start: PointT
    end: PointT
    duration: timedelta = timedelta(milliseconds=500)

    def __post_init__(self) -> None:
        if self.start is None or self.end is None:
            raise TypeError("touch drag-and-drop points cannot be None")
        object.__setattr__(
            self,
            "duration",
            _normalize_positive_duration(
                self.duration, field_name="touch drag-and-drop duration"
            ),
        )


__all__ = ["TouchDragAndDrop", "TouchLongPress", "TouchSwipe", "TouchTap"]
