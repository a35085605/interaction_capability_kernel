"""Windows-native atomic command contracts."""

from windows.command.domain import (
    WindowActivation,
    WindowBoundsChange,
    WindowMinimize,
    WindowMove,
    WindowResize,
    WindowRestore,
)
from windows.command.ports import (
    WindowActivator,
    WindowBoundsController,
    WindowMinimizer,
    WindowMover,
    WindowResizer,
    WindowRestorer,
)

__all__ = [
    "WindowActivation",
    "WindowActivator",
    "WindowBoundsChange",
    "WindowBoundsController",
    "WindowMinimize",
    "WindowMinimizer",
    "WindowMove",
    "WindowMover",
    "WindowResize",
    "WindowResizer",
    "WindowRestore",
    "WindowRestorer",
]
