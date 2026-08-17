from __future__ import annotations

from dataclasses import dataclass
import math
from numbers import Real
from typing import Self

from geometry.point import Point
from geometry.rect import Rect


def _normalize_finite_real(
    value: object,
    *,
    field_name: str,
    positive: bool = False,
) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{field_name} must be a real number")
    normalized = float(value)
    if not math.isfinite(normalized):
        raise ValueError(f"{field_name} must be finite")
    if positive and normalized <= 0.0:
        raise ValueError(f"{field_name} must be positive")
    return normalized


@dataclass(frozen=True, slots=True)
class AxisAlignedTransform:
    """Generic axis-aligned scale and translation between coordinate spaces."""

    scale_x: float
    scale_y: float
    offset_x: float = 0.0
    offset_y: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "scale_x",
            _normalize_finite_real(
                self.scale_x,
                field_name="scale_x",
                positive=True,
            ),
        )
        object.__setattr__(
            self,
            "scale_y",
            _normalize_finite_real(
                self.scale_y,
                field_name="scale_y",
                positive=True,
            ),
        )
        object.__setattr__(
            self,
            "offset_x",
            _normalize_finite_real(self.offset_x, field_name="offset_x"),
        )
        object.__setattr__(
            self,
            "offset_y",
            _normalize_finite_real(self.offset_y, field_name="offset_y"),
        )

    @classmethod
    def identity(cls) -> Self:
        """Return an identity transform."""

        return cls(scale_x=1.0, scale_y=1.0)

    @classmethod
    def from_rects(cls, source: Rect, target: Rect) -> Self:
        """Return the transform that maps ``source`` bounds exactly to ``target``."""

        if not isinstance(source, Rect):
            raise TypeError("source must be Rect")
        if not isinstance(target, Rect):
            raise TypeError("target must be Rect")

        scale_x = target.width / source.width
        scale_y = target.height / source.height
        return cls(
            scale_x=scale_x,
            scale_y=scale_y,
            offset_x=target.left - source.left * scale_x,
            offset_y=target.top - source.top * scale_y,
        )

    def map_xy(self, x: Real, y: Real) -> tuple[float, float]:
        """Map one coordinate pair into the target space without quantization."""

        return (
            float(x) * self.scale_x + self.offset_x,
            float(y) * self.scale_y + self.offset_y,
        )

    def map_point(self, point: Point) -> Point:
        """Map one point into the target space without quantization."""

        if not isinstance(point, Point):
            raise TypeError("point must be Point")
        x, y = self.map_xy(point.x, point.y)
        return Point(x=x, y=y)

    def inverse_xy(self, x: Real, y: Real) -> tuple[float, float]:
        """Map one coordinate pair back into the source space."""

        return (
            (float(x) - self.offset_x) / self.scale_x,
            (float(y) - self.offset_y) / self.scale_y,
        )

    def inverse_point(self, point: Point) -> Point:
        """Map one point back into the source space without quantization."""

        if not isinstance(point, Point):
            raise TypeError("point must be Point")
        x, y = self.inverse_xy(point.x, point.y)
        return Point(x=x, y=y)

    def map_rect_exact(self, rect: Rect) -> Rect:
        """Map ``rect`` when every transformed half-open edge is integral."""

        if not isinstance(rect, Rect):
            raise TypeError("rect must be Rect")

        left, top = self.map_xy(rect.left, rect.top)
        right, bottom = self.map_xy(rect.right, rect.bottom)
        mapped_edges = (left, top, right, bottom)
        rounded_edges = tuple(round(value) for value in mapped_edges)
        if not all(
            math.isclose(value, rounded, rel_tol=0.0, abs_tol=1e-9)
            for value, rounded in zip(mapped_edges, rounded_edges)
        ):
            raise ValueError("mapped rectangle edges must be integer coordinates")

        mapped_left, mapped_top, mapped_right, mapped_bottom = (
            int(value) for value in rounded_edges
        )
        return Rect.from_ltrb(
            left=mapped_left,
            top=mapped_top,
            right=mapped_right,
            bottom=mapped_bottom,
        )

    def map_rect_enclosing(self, rect: Rect) -> Rect:
        """Map ``rect`` to the smallest integer half-open Rect that contains it."""

        if not isinstance(rect, Rect):
            raise TypeError("rect must be Rect")

        left, top = self.map_xy(rect.left, rect.top)
        right, bottom = self.map_xy(rect.right, rect.bottom)
        return Rect.from_ltrb(
            left=math.floor(left),
            top=math.floor(top),
            right=math.ceil(right),
            bottom=math.ceil(bottom),
        )

    def inverse(self) -> Self:
        """Return the inverse target-to-source transform."""

        return type(self)(
            scale_x=1.0 / self.scale_x,
            scale_y=1.0 / self.scale_y,
            offset_x=-self.offset_x / self.scale_x,
            offset_y=-self.offset_y / self.scale_y,
        )

    def then(self, outer: AxisAlignedTransform) -> Self:
        """Return the transform that applies ``self`` and then ``outer``."""

        if not isinstance(outer, AxisAlignedTransform):
            raise TypeError("outer must be AxisAlignedTransform")

        return type(self)(
            scale_x=self.scale_x * outer.scale_x,
            scale_y=self.scale_y * outer.scale_y,
            offset_x=self.offset_x * outer.scale_x + outer.offset_x,
            offset_y=self.offset_y * outer.scale_y + outer.offset_y,
        )


__all__ = ["AxisAlignedTransform"]
