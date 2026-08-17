from __future__ import annotations

from dataclasses import dataclass
import math
from numbers import Real
from typing import Self


def _normalize_finite_real(value: object, *, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{field_name} must be a real number")
    normalized = float(value)
    if not math.isfinite(normalized):
        raise ValueError(f"{field_name} must be finite")
    return normalized


@dataclass(frozen=True, slots=True)
class Point:
    """Continuous point in a caller-owned numeric frame."""

    x: float
    y: float

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "x",
            _normalize_finite_real(self.x, field_name="point x"),
        )
        object.__setattr__(
            self,
            "y",
            _normalize_finite_real(self.y, field_name="point y"),
        )

    def as_tuple(self) -> tuple[float, float]:
        return self.x, self.y

    def translated(
        self,
        *,
        dx: Real = 0.0,
        dy: Real = 0.0,
    ) -> Self:
        return type(self)(
            x=self.x + _normalize_finite_real(dx, field_name="translation dx"),
            y=self.y + _normalize_finite_real(dy, field_name="translation dy"),
        )


@dataclass(frozen=True, slots=True)
class RelativePoint:

    x_ratio: float
    y_ratio: float

    def clamp(self) -> "RelativePoint":
        return RelativePoint(
            x_ratio=max(0.0, min(1.0, float(self.x_ratio))),
            y_ratio=max(0.0, min(1.0, float(self.y_ratio))),
        )

    def to_point(self, *, width: int, height: int) -> Point:
        if width <= 0 or height <= 0:
            raise ValueError(f"width/height must be positive integers, received {width}x{height}")
        c = self.clamp()
        x = int(round(c.x_ratio * width))
        y = int(round(c.y_ratio * height))
        x = max(0, min(x, width - 1))
        y = max(0, min(y, height - 1))
        return Point(x=x, y=y)
