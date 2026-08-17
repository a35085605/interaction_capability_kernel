from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from numbers import Integral

from geometry import LocalPlacement, Rect
from windows.identity import WindowId
from windows.spatial.desktop import DesktopVirtualScreenSurface
from windows.spatial.window import WindowClientSurface


class DesktopForegroundStatus(str, Enum):
    """Whether the desktop foreground Window is known, absent, or identified."""

    UNKNOWN = "unknown"
    NONE = "none"
    WINDOW = "window"


@dataclass(frozen=True, slots=True)
class DesktopState:
    """Observed Windows desktop-global facts.

    No desktop-session identity is introduced until the framework needs to
    distinguish actual operating-system sessions or security environments.
    """

    foreground_status: DesktopForegroundStatus = DesktopForegroundStatus.UNKNOWN
    foreground_window_id: WindowId | None = None
    virtual_screen: DesktopVirtualScreenSurface | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.foreground_status, DesktopForegroundStatus):
            raise TypeError("foreground_status must be DesktopForegroundStatus")
        if self.foreground_window_id is not None and not isinstance(
            self.foreground_window_id,
            WindowId,
        ):
            raise TypeError("foreground_window_id must be WindowId or None")
        if self.virtual_screen is not None and not isinstance(
            self.virtual_screen,
            DesktopVirtualScreenSurface,
        ):
            raise TypeError(
                "virtual_screen must be DesktopVirtualScreenSurface or None"
            )

        if self.foreground_status is DesktopForegroundStatus.WINDOW:
            if self.foreground_window_id is None:
                raise ValueError(
                    "window foreground status requires foreground_window_id"
                )
        elif self.foreground_window_id is not None:
            raise ValueError(
                "foreground_window_id is only valid for window foreground status"
            )


def _normalize_optional_text(
    value: object,
    *,
    field_name: str,
) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(
            f"{field_name} must be a string, got {type(value).__name__}"
        )
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} cannot be empty")
    return normalized


def _validate_optional_bool(
    value: object,
    *,
    field_name: str,
) -> bool | None:
    if value is not None and not isinstance(value, bool):
        raise TypeError(f"{field_name} must be bool or None")
    return value


def _validate_optional_process_id(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError("window process id must be an integer or None")
    normalized = int(value)
    if normalized <= 0:
        raise ValueError("window process id must be greater than zero")
    return normalized


def _validate_optional_rect(
    value: object,
    *,
    field_name: str,
) -> Rect | None:
    if value is not None and not isinstance(value, Rect):
        raise TypeError(f"{field_name} must be Rect or None")
    return value


@dataclass(frozen=True, slots=True)
class WindowState:
    """Native state of one Window.

    Foreground ownership is desktop-global state and therefore is not represented
    here. Application-presentation location is a separate caller-composed
    interpretation of ``client_surface``.
    """

    window_id: WindowId
    process_id: int | None = None
    title: str | None = None
    bounds_virtual_screen: Rect | None = None
    client_surface: WindowClientSurface | None = None
    minimized: bool | None = None
    visible: bool | None = None
    responsive: bool | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.window_id, WindowId):
            raise TypeError("window_id must be WindowId")
        process_id = _validate_optional_process_id(self.process_id)
        title = _normalize_optional_text(self.title, field_name="window title")
        bounds_virtual_screen = _validate_optional_rect(
            self.bounds_virtual_screen,
            field_name="window bounds",
        )
        client_surface = self.client_surface
        if client_surface is not None and not isinstance(
            client_surface,
            WindowClientSurface,
        ):
            raise TypeError("client_surface must be WindowClientSurface or None")
        minimized = _validate_optional_bool(
            self.minimized,
            field_name="window minimized",
        )
        visible = _validate_optional_bool(
            self.visible,
            field_name="window visible",
        )
        responsive = _validate_optional_bool(
            self.responsive,
            field_name="window responsive",
        )

        if client_surface is not None:
            if client_surface.window_id != self.window_id:
                raise ValueError("window client surface must belong to window id")
            if (
                bounds_virtual_screen is not None
                and client_surface.bounds_virtual_screen is not None
                and not bounds_virtual_screen.contains_rect(
                    client_surface.bounds_virtual_screen
                )
            ):
                raise ValueError("window bounds must contain client bounds")

        object.__setattr__(self, "process_id", process_id)
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "bounds_virtual_screen", bounds_virtual_screen)
        object.__setattr__(self, "client_surface", client_surface)
        object.__setattr__(self, "minimized", minimized)
        object.__setattr__(self, "visible", visible)
        object.__setattr__(self, "responsive", responsive)

    @property
    def client_bounds_virtual_screen(self) -> Rect | None:
        if self.client_surface is None:
            return None
        return self.client_surface.bounds_virtual_screen

    @property
    def client_placement_virtual_screen(self) -> LocalPlacement | None:
        if self.client_surface is None:
            return None
        return self.client_surface.placement_virtual_screen


__all__ = ["DesktopForegroundStatus", "DesktopState", "WindowState"]
