"""Microsoft Windows native-domain vocabulary and atomic queries."""

from windows.identity import WindowId
from windows.query import DesktopInspector, WindowInspector

__all__ = ["DesktopInspector", "WindowId", "WindowInspector"]
