from __future__ import annotations

import unittest

from android.display import AndroidDisplayId
from android.spatial import AndroidDisplaySurface
from android.presentation import (
    ApplicationPresentationInAndroidDisplayFailureReason,
    ApplicationPresentationInAndroidDisplayUnavailable,
    LocatedApplicationPresentationInAndroidDisplay,
    locate_application_presentation_in_android_display,
)
from app.presentation import ApplicationPresentationCorrespondenceAnchor
from app.presentation.adapters import ConfiguredApplicationPresentationLocator
from geometry import Rect


class AndroidPresentationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.anchor = ApplicationPresentationCorrespondenceAnchor("primary")
        self.surface = AndroidDisplaySurface(
            display_id=AndroidDisplayId(0),
            bounds=Rect(x=0, y=0, width=1080, height=2400),
        )

    def test_locator_interprets_native_display_surface(self) -> None:
        located = locate_application_presentation_in_android_display(
            self.surface,
            anchor=self.anchor,
            locator=ConfiguredApplicationPresentationLocator(
                bounds=Rect(x=0, y=100, width=1080, height=2200)
            ),
        )

        self.assertIsInstance(located, LocatedApplicationPresentationInAndroidDisplay)
        assert isinstance(located, LocatedApplicationPresentationInAndroidDisplay)
        self.assertIs(located.presentation.surface, self.surface)
        self.assertEqual(located.presentation.display_id, self.surface.display_id)
        self.assertEqual(
            located.presentation.bounds_display,
            Rect(x=0, y=100, width=1080, height=2200),
        )
        self.assertEqual(located.presentation.presentation.anchor, self.anchor)

    def test_outside_bounds_are_surface_specific_failure(self) -> None:
        result = locate_application_presentation_in_android_display(
            self.surface,
            anchor=self.anchor,
            locator=ConfiguredApplicationPresentationLocator(
                bounds=Rect(x=0, y=100, width=1080, height=2400)
            ),
        )

        self.assertIsInstance(result, ApplicationPresentationInAndroidDisplayUnavailable)
        assert isinstance(result, ApplicationPresentationInAndroidDisplayUnavailable)
        self.assertEqual(
            result.reason,
            ApplicationPresentationInAndroidDisplayFailureReason.BOUNDS_OUTSIDE_DISPLAY,
        )


class AndroidPresentationImportBoundaryTests(unittest.TestCase):
    def test_android_presentation_does_not_load_adb(self) -> None:
        import subprocess
        import sys

        script = """
import sys
import android.presentation

assert 'adb' not in sys.modules
"""
        subprocess.run([sys.executable, "-c", script], check=True)


if __name__ == "__main__":
    unittest.main()
