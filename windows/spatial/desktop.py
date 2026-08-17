from __future__ import annotations

from dataclasses import dataclass
from numbers import Integral

from geometry import Rect


def _normalize_integer(value: object, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError(
            f"{field_name} must be an integer, got {type(value).__name__}"
        )
    return int(value)


@dataclass(frozen=True, slots=True, order=True)
class ScreenPoint:
    """Point in operating-system desktop virtual-screen coordinates."""

    x: int
    y: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "x",
            _normalize_integer(self.x, field_name="screen point x"),
        )
        object.__setattr__(
            self,
            "y",
            _normalize_integer(self.y, field_name="screen point y"),
        )


@dataclass(frozen=True, slots=True)
class DesktopVirtualScreenSurface:
    """Current desktop virtual-screen spatial surface.

    The surface owns only the observed root bounds used by desktop-coordinate
    native operations. It does not identify a desktop session, establish
    freshness, or say that an operation may target a particular Window.
    """

    bounds: Rect

    def __post_init__(self) -> None:
        if not isinstance(self.bounds, Rect):
            raise TypeError("desktop virtual-screen bounds must be Rect")


__all__ = ["DesktopVirtualScreenSurface", "ScreenPoint"]
