from __future__ import annotations

import unittest

from geometry import LocalPlacement, Point, Rect
from windows import WindowId
from windows.spatial.window import WindowClientPoint, WindowClientSurface
from windows.state import WindowState


class WindowStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.window_id = WindowId("window-1")
        self.client_bounds = Rect(x=0, y=0, width=800, height=600)
        self.placement = LocalPlacement.from_rects(
            local_bounds=self.client_bounds,
            bounds_root=Rect(x=100, y=200, width=800, height=600),
        )
        self.client = WindowClientSurface(
            window_id=self.window_id,
            bounds=self.client_bounds,
            placement_virtual_screen=self.placement,
        )

    def test_window_client_surface_has_optional_virtual_screen_placement(self) -> None:
        self.assertEqual(self.client.window_id, self.window_id)
        self.assertEqual(self.client.bounds, self.client_bounds)
        self.assertEqual(
            self.client.bounds_virtual_screen,
            Rect(x=100, y=200, width=800, height=600),
        )
        self.assertEqual(
            self.client.placement_virtual_screen.map_point_to_root(Point(x=10, y=20)),
            Point(x=110, y=220),
        )

    def test_window_state_owns_only_native_window_facts(self) -> None:
        state = WindowState(
            window_id=self.window_id,
            bounds_virtual_screen=Rect(x=90, y=160, width=840, height=660),
            client_surface=self.client,
        )

        self.assertEqual(
            state.client_bounds_virtual_screen,
            self.client.bounds_virtual_screen,
        )
        self.assertIs(state.client_placement_virtual_screen, self.placement)
        self.assertFalse(hasattr(state, "application_presentation"))

    def test_client_local_execution_does_not_require_screen_placement(self) -> None:
        client = WindowClientSurface(
            window_id=self.window_id,
            bounds=self.client_bounds,
        )
        state = WindowState(
            window_id=self.window_id,
            client_surface=client,
        )

        self.assertIsNone(state.client_bounds_virtual_screen)
        self.assertIsNone(state.client_placement_virtual_screen)

    def test_window_client_surface_must_belong_to_window(self) -> None:
        with self.assertRaisesRegex(ValueError, "must belong to window id"):
            WindowState(
                window_id=WindowId("window-2"),
                client_surface=self.client,
            )

    def test_window_client_point_has_window_specific_type(self) -> None:
        point = WindowClientPoint(x=12, y=34)
        self.assertEqual((point.x, point.y), (12, 34))


if __name__ == "__main__":
    unittest.main()
