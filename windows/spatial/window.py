from __future__ import annotations

from dataclasses import dataclass
from numbers import Integral

from geometry import LocalPlacement, Rect
from windows.identity import WindowId


def _normalize_integer(value: object, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError(
            f"{field_name} must be an integer, got {type(value).__name__}"
        )
    return int(value)


@dataclass(frozen=True, slots=True, order=True)
class WindowClientPoint:
    """Point in one window-client local numeric frame."""

    x: int
    y: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "x",
            _normalize_integer(self.x, field_name="window client point x"),
        )
        object.__setattr__(
            self,
            "y",
            _normalize_integer(self.y, field_name="window client point y"),
        )


@dataclass(frozen=True, slots=True)
class WindowClientSurface:
    """Current client-area spatial surface of one native Window.

    ``bounds`` is expressed in client-local coordinates. The optional placement
    maps that local surface into the desktop virtual-screen root. Window identity
    remains domain-owned rather than becoming coordinate-space identity.
    """

    window_id: WindowId
    bounds: Rect
    placement_virtual_screen: LocalPlacement | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.window_id, WindowId):
            raise TypeError("window_id must be WindowId")
        if not isinstance(self.bounds, Rect):
            raise TypeError("window client bounds must be Rect")
        if self.placement_virtual_screen is not None:
            if not isinstance(self.placement_virtual_screen, LocalPlacement):
                raise TypeError(
                    "placement_virtual_screen must be LocalPlacement or None"
                )
            if self.placement_virtual_screen.local_bounds != self.bounds:
                raise ValueError(
                    "virtual-screen placement local bounds must equal "
                    "window client bounds"
                )

    @property
    def bounds_virtual_screen(self) -> Rect | None:
        if self.placement_virtual_screen is None:
            return None
        return self.placement_virtual_screen.bounds_root


__all__ = ["WindowClientPoint", "WindowClientSurface"]
