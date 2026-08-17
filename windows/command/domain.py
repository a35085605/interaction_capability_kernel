from __future__ import annotations

from dataclasses import dataclass

from geometry.rect import Rect
from geometry.size import Size
from windows.identity import WindowId
from windows.spatial.desktop import ScreenPoint


def _validate_window_id(value: object) -> WindowId:
    if not isinstance(value, WindowId):
        raise TypeError("window_id must be WindowId")
    return value


@dataclass(frozen=True, slots=True)
class WindowActivation:
    """Request platform activation; this is not a focus guarantee."""

    window_id: WindowId

    def __post_init__(self) -> None:
        object.__setattr__(self, "window_id", _validate_window_id(self.window_id))


@dataclass(frozen=True, slots=True)
class WindowMinimize:
    window_id: WindowId

    def __post_init__(self) -> None:
        object.__setattr__(self, "window_id", _validate_window_id(self.window_id))


@dataclass(frozen=True, slots=True)
class WindowRestore:
    """Request the platform to restore a minimized window."""

    window_id: WindowId

    def __post_init__(self) -> None:
        object.__setattr__(self, "window_id", _validate_window_id(self.window_id))


@dataclass(frozen=True, slots=True)
class WindowMove:
    window_id: WindowId
    top_left_screen: ScreenPoint

    def __post_init__(self) -> None:
        object.__setattr__(self, "window_id", _validate_window_id(self.window_id))
        if not isinstance(self.top_left_screen, ScreenPoint):
            raise TypeError("top_left_screen must be ScreenPoint")


@dataclass(frozen=True, slots=True)
class WindowResize:
    window_id: WindowId
    size: Size

    def __post_init__(self) -> None:
        object.__setattr__(self, "window_id", _validate_window_id(self.window_id))
        if not isinstance(self.size, Size):
            raise TypeError("window resize size must be Size")


@dataclass(frozen=True, slots=True)
class WindowBoundsChange:
    """Atomically request a new outer Window rectangle when supported."""

    window_id: WindowId
    bounds_screen: Rect

    def __post_init__(self) -> None:
        object.__setattr__(self, "window_id", _validate_window_id(self.window_id))
        if not isinstance(self.bounds_screen, Rect):
            raise TypeError("bounds_screen must be Rect")
