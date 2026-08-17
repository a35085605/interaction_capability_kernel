from __future__ import annotations

from dataclasses import dataclass

from geometry.point import Point
from geometry.rect import Rect
from geometry.transform import AxisAlignedTransform


@dataclass(frozen=True, slots=True)
class LocalPlacement:
    """Map a local numeric frame into its owning domain's root frame.

    The placement is canonically defined by its local and root bounds. The
    axis-aligned transform between them is derived from those bounds. The owning
    domain defines the root's meaning.
    """

    local_bounds: Rect
    bounds_root: Rect

    def __post_init__(self) -> None:
        if not isinstance(self.local_bounds, Rect):
            raise TypeError("local_bounds must be Rect")
        if not isinstance(self.bounds_root, Rect):
            raise TypeError("bounds_root must be Rect")

    @property
    def local_to_root(self) -> AxisAlignedTransform:
        return AxisAlignedTransform.from_rects(
            self.local_bounds,
            self.bounds_root,
        )

    @classmethod
    def from_rects(
        cls,
        *,
        local_bounds: Rect,
        bounds_root: Rect,
    ) -> LocalPlacement:
        return cls(
            local_bounds=local_bounds,
            bounds_root=bounds_root,
        )

    def map_point_to_root(self, point: Point) -> Point:
        if not isinstance(point, Point):
            raise TypeError("point must be Point")
        if not self.local_bounds.contains_point(point):
            raise ValueError("point must be inside local_bounds")
        return self.local_to_root.map_point(point)

    def map_rect_to_root(self, rect: Rect) -> Rect:
        if not isinstance(rect, Rect):
            raise TypeError("rect must be Rect")
        if not self.local_bounds.contains_rect(rect):
            raise ValueError("rect must be inside local_bounds")
        return self.local_to_root.map_rect_enclosing(rect)


__all__ = ["LocalPlacement"]
