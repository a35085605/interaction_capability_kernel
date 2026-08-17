from __future__ import annotations

import unittest

from windows.spatial.desktop import ScreenPoint
from windows import WindowId
from windows.command import WindowActivation, WindowMove


class WindowCommandTests(unittest.TestCase):
    def test_commands_use_native_window_identity(self) -> None:
        window_id = WindowId("window-1")
        activation = WindowActivation(window_id=window_id)
        self.assertEqual(activation.window_id, window_id)

    def test_window_move_uses_desktop_screen_point(self) -> None:
        operation = WindowMove(
            window_id=WindowId("window-1"),
            top_left_screen=ScreenPoint(x=-100, y=20),
        )
        self.assertEqual(operation.top_left_screen, ScreenPoint(x=-100, y=20))

    def test_raw_window_id_is_rejected(self) -> None:
        with self.assertRaisesRegex(TypeError, "window_id must be WindowId"):
            WindowActivation(window_id="window-1")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
