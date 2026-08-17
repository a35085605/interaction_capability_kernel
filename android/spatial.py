from __future__ import annotations

from dataclasses import dataclass
from numbers import Integral

from android.display import AndroidDisplayId
from geometry import Rect


def _normalize_integer(value: object, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError(
            f"{field_name} must be an integer, got {type(value).__name__}"
        )
    return int(value)


@dataclass(frozen=True, slots=True, order=True)
class AndroidDisplayPoint:
    """Point in one Android logical-display coordinate surface."""

    x: int
    y: int

    def __post_init__(self) -> None:
        x = _normalize_integer(self.x, field_name="Android display point x")
        y = _normalize_integer(self.y, field_name="Android display point y")
        if x < 0 or y < 0:
            raise ValueError("Android display point coordinates cannot be negative")
        object.__setattr__(self, "x", x)
        object.__setattr__(self, "y", y)


@dataclass(frozen=True, slots=True)
class AndroidDisplaySurface:
    """Current logical coordinate surface of one Android display."""

    display_id: AndroidDisplayId
    bounds: Rect

    def __post_init__(self) -> None:
        if not isinstance(self.display_id, AndroidDisplayId):
            raise TypeError("display_id must be AndroidDisplayId")
        if not isinstance(self.bounds, Rect):
            raise TypeError("Android display bounds must be Rect")


__all__ = ["AndroidDisplayPoint", "AndroidDisplaySurface"]
