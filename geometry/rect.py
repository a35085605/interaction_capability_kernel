from __future__ import annotations

from dataclasses import dataclass
from numbers import Integral
from typing import Self

from geometry.point import Point


def _normalize_integer(
    value: object,
    *,
    field_name: str,
) -> int:
    """
    Accept Python and NumPy integer values, but reject bool.

    bool must be rejected explicitly because it is a subclass of int.
    """
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError(
            f"{field_name} must be an integer, "
            f"got {type(value).__name__}"
        )

    return int(value)


@dataclass(frozen=True, slots=True)
class Rect:
    """
    Immutable axis-aligned rectangle using half-open coordinates.

    Horizontal range:
        [left, right)

    Vertical range:
        [top, bottom)

    Therefore:

    - right = x + width
    - bottom = y + height
    - width and height must be positive
    - rectangles touching only at an edge do not intersect
    """

    x: int
    y: int
    width: int
    height: int

    def __post_init__(self) -> None:
        x = _normalize_integer(
            self.x,
            field_name="rect x",
        )
        y = _normalize_integer(
            self.y,
            field_name="rect y",
        )
        width = _normalize_integer(
            self.width,
            field_name="rect width",
        )
        height = _normalize_integer(
            self.height,
            field_name="rect height",
        )

        if width <= 0:
            raise ValueError(
                "rect width must be greater than zero"
            )

        if height <= 0:
            raise ValueError(
                "rect height must be greater than zero"
            )

        object.__setattr__(self, "x", x)
        object.__setattr__(self, "y", y)
        object.__setattr__(self, "width", width)
        object.__setattr__(self, "height", height)

    @classmethod
    def from_ltrb(
        cls,
        *,
        left: int,
        top: int,
        right: int,
        bottom: int,
    ) -> Self:
        left = _normalize_integer(
            left,
            field_name="rect left",
        )
        top = _normalize_integer(
            top,
            field_name="rect top",
        )
        right = _normalize_integer(
            right,
            field_name="rect right",
        )
        bottom = _normalize_integer(
            bottom,
            field_name="rect bottom",
        )

        if right <= left:
            raise ValueError(
                "rect right must be greater than left"
            )

        if bottom <= top:
            raise ValueError(
                "rect bottom must be greater than top"
            )

        return cls(
            x=left,
            y=top,
            width=right - left,
            height=bottom - top,
        )

    @property
    def left(self) -> int:
        return self.x

    @property
    def top(self) -> int:
        return self.y

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    @property
    def area(self) -> int:
        return self.width * self.height

    @property
    def center_x(self) -> float:
        return self.x + self.width / 2

    @property
    def center_y(self) -> float:
        return self.y + self.height / 2

    @property
    def center(self) -> Point:
        return Point(x=self.center_x, y=self.center_y)

    def contains_point(
        self,
        point: Point,
    ) -> bool:
        if not isinstance(point, Point):
            raise TypeError(
                "point must be Point, "
                f"got {type(point).__name__}"
            )

        return (
            self.left <= point.x < self.right
            and self.top <= point.y < self.bottom
        )

    def contains_rect(
        self,
        other: Rect,
    ) -> bool:
        self._validate_other(other)

        return (
            self.left <= other.left
            and self.top <= other.top
            and other.right <= self.right
            and other.bottom <= self.bottom
        )

    def intersects(
        self,
        other: Rect,
    ) -> bool:
        self._validate_other(other)

        return (
            self.left < other.right
            and other.left < self.right
            and self.top < other.bottom
            and other.top < self.bottom
        )

    def intersection(
        self,
        other: Rect,
    ) -> Rect | None:
        self._validate_other(other)

        left = max(self.left, other.left)
        top = max(self.top, other.top)
        right = min(self.right, other.right)
        bottom = min(self.bottom, other.bottom)

        if right <= left or bottom <= top:
            return None

        return Rect.from_ltrb(
            left=left,
            top=top,
            right=right,
            bottom=bottom,
        )

    def intersection_area(
        self,
        other: Rect,
    ) -> int:
        intersection = self.intersection(other)

        if intersection is None:
            return 0

        return intersection.area

    def iou(
        self,
        other: Rect,
    ) -> float:
        """
        Intersection over Union.
        """
        self._validate_other(other)

        intersection_area = self.intersection_area(other)

        if intersection_area == 0:
            return 0.0

        union_area = (
            self.area
            + other.area
            - intersection_area
        )

        return intersection_area / union_area

    def translated(
        self,
        *,
        dx: int = 0,
        dy: int = 0,
    ) -> Rect:
        dx = _normalize_integer(
            dx,
            field_name="translation dx",
        )
        dy = _normalize_integer(
            dy,
            field_name="translation dy",
        )

        return Rect(
            x=self.x + dx,
            y=self.y + dy,
            width=self.width,
            height=self.height,
        )

    @staticmethod
    def _validate_other(
        other: object,
    ) -> None:
        if not isinstance(other, Rect):
            raise TypeError(
                "other must be Rect, "
                f"got {type(other).__name__}"
            )
