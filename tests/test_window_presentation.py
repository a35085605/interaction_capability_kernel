from __future__ import annotations

import unittest

from app.presentation import ApplicationPresentationCorrespondenceAnchor
from app.presentation.adapters import ConfiguredApplicationPresentationLocator
from geometry import Rect
from windows import WindowId
from windows.spatial.window import WindowClientSurface
from windows.state import WindowState
from windows.presentation import (
    ApplicationPresentationInWindowFailureReason,
    ApplicationPresentationInWindowUnavailable,
    LocatedApplicationPresentationInWindow,
    locate_application_presentation_in_window,
)


class WindowPresentationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.anchor = ApplicationPresentationCorrespondenceAnchor("primary")
        self.window_id = WindowId("window-1")
        self.window = WindowState(
            window_id=self.window_id,
            client_surface=WindowClientSurface(
                window_id=self.window_id,
                bounds=Rect(x=0, y=0, width=800, height=600),
            ),
        )

    def test_locator_interprets_native_window_surface(self) -> None:
        located = locate_application_presentation_in_window(
            self.window,
            anchor=self.anchor,
            locator=ConfiguredApplicationPresentationLocator(
                bounds=Rect(x=20, y=30, width=640, height=480)
            ),
        )

        self.assertIsInstance(located, LocatedApplicationPresentationInWindow)
        assert isinstance(located, LocatedApplicationPresentationInWindow)
        self.assertIs(located.presentation.surface, self.window.client_surface)
        self.assertEqual(located.presentation.window_id, self.window_id)
        self.assertEqual(
            located.presentation.bounds_client,
            Rect(x=20, y=30, width=640, height=480),
        )
        self.assertEqual(located.presentation.presentation.anchor, self.anchor)

    def test_outside_bounds_are_surface_specific_failure(self) -> None:
        result = locate_application_presentation_in_window(
            self.window,
            anchor=self.anchor,
            locator=ConfiguredApplicationPresentationLocator(
                bounds=Rect(x=0, y=0, width=801, height=600)
            ),
        )

        self.assertIsInstance(result, ApplicationPresentationInWindowUnavailable)
        assert isinstance(result, ApplicationPresentationInWindowUnavailable)
        self.assertEqual(
            result.reason,
            ApplicationPresentationInWindowFailureReason.BOUNDS_OUTSIDE_CLIENT,
        )

    def test_client_surface_is_required_to_bind_client_local_geometry(self) -> None:
        window = WindowState(window_id=self.window_id)
        result = locate_application_presentation_in_window(
            window,
            anchor=self.anchor,
            locator=ConfiguredApplicationPresentationLocator(
                bounds=Rect(x=0, y=0, width=1, height=1)
            ),
        )

        self.assertIsInstance(result, ApplicationPresentationInWindowUnavailable)
        assert isinstance(result, ApplicationPresentationInWindowUnavailable)
        self.assertEqual(
            result.reason,
            ApplicationPresentationInWindowFailureReason.CLIENT_SURFACE_UNAVAILABLE,
        )


if __name__ == "__main__":
    unittest.main()
