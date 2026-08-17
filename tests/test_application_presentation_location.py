from __future__ import annotations

import unittest

from app.presentation import (
    ApplicationPresentationLocationProvenance,
    LocatedApplicationPresentationInSurface,
)
from app.presentation.adapters import ConfiguredApplicationPresentationLocator
from geometry import Rect


class ApplicationPresentationLocationTests(unittest.TestCase):
    def test_configured_locator_binds_result_to_supplied_surface(self) -> None:
        surface = object()
        bounds = Rect(x=10, y=20, width=300, height=200)
        locator = ConfiguredApplicationPresentationLocator[object](bounds=bounds)

        located = locator.locate(surface)

        self.assertIsInstance(located, LocatedApplicationPresentationInSurface)
        assert isinstance(located, LocatedApplicationPresentationInSurface)
        self.assertIs(located.surface, surface)
        self.assertEqual(located.bounds, bounds)
        self.assertEqual(
            located.provenance,
            ApplicationPresentationLocationProvenance(
                "application_presentation.configured"
            ),
        )


if __name__ == "__main__":
    unittest.main()
