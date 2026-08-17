from __future__ import annotations

from typing import Protocol

from windows.identity import WindowId
from windows.state import DesktopState, WindowState


class DesktopInspector(Protocol):
    """Read-only inspector for current Windows desktop-global native facts."""

    def inspect(self) -> DesktopState:
        ...


class WindowInspector(Protocol):
    """Read-only inspector for one native Window identity."""

    def inspect(self, window_id: WindowId) -> WindowState | None:
        """Return current Window facts, or ``None`` when it is not observed."""
        ...


__all__ = ["DesktopInspector", "WindowInspector"]
