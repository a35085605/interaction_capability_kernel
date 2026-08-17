from __future__ import annotations

import unittest

from windows.spatial.desktop import DesktopVirtualScreenSurface
from windows.state import DesktopForegroundStatus, DesktopState
from geometry import Rect
from windows import WindowId


class DesktopStateTests(unittest.TestCase):
    def test_virtual_screen_is_a_spatial_surface_fact(self) -> None:
        surface = DesktopVirtualScreenSurface(
            bounds=Rect(x=-1920, y=0, width=3840, height=1080)
        )
        state = DesktopState(virtual_screen=surface)

        self.assertIs(state.virtual_screen, surface)

    def test_foreground_window_is_desktop_global_fact(self) -> None:
        window_id = WindowId("window-1")
        state = DesktopState(
            foreground_status=DesktopForegroundStatus.WINDOW,
            foreground_window_id=window_id,
        )
        self.assertEqual(state.foreground_window_id, window_id)

    def test_window_status_requires_window_identity(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires foreground_window_id"):
            DesktopState(foreground_status=DesktopForegroundStatus.WINDOW)

    def test_none_and_unknown_do_not_accept_window_identity(self) -> None:
        for status in (
            DesktopForegroundStatus.NONE,
            DesktopForegroundStatus.UNKNOWN,
        ):
            with self.subTest(status=status):
                with self.assertRaisesRegex(ValueError, "only valid"):
                    DesktopState(
                        foreground_status=status,
                        foreground_window_id=WindowId("window-1"),
                    )


if __name__ == "__main__":
    unittest.main()
