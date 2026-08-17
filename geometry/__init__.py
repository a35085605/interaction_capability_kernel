"""Stable geometry primitives shared across capability packages."""

from geometry.placement import LocalPlacement
from geometry.point import Point, RelativePoint
from geometry.rect import Rect
from geometry.size import Size
from geometry.transform import AxisAlignedTransform

__all__ = [
    "AxisAlignedTransform",
    "LocalPlacement",
    "Point",
    "Rect",
    "RelativePoint",
    "Size",
]
