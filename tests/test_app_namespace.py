from __future__ import annotations

import unittest

from app import ApplicationId
from app.layout import LayoutScalingStability
from app.raster import ApplicationPresentationRaster
from app.presentation import (
    ApplicationPresentation,
    ApplicationPresentationCorrespondenceAnchor,
)


class AppNamespaceTests(unittest.TestCase):
    def test_application_id_normalizes_non_empty_text(self) -> None:
        application_id = ApplicationId("  example.app  ")

        self.assertEqual(application_id.value, "example.app")
        self.assertEqual(str(application_id), "example.app")

    def test_application_id_rejects_empty_text(self) -> None:
        with self.assertRaisesRegex(ValueError, "application id cannot be empty"):
            ApplicationId("   ")

    def test_correspondence_anchor_normalizes_non_empty_text(self) -> None:
        anchor = ApplicationPresentationCorrespondenceAnchor(
            "  primary-presentation-correspondence  "
        )

        self.assertEqual(anchor.value, "primary-presentation-correspondence")
        self.assertEqual(str(anchor), "primary-presentation-correspondence")

    def test_correspondence_anchor_rejects_empty_text(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "application presentation correspondence anchor cannot be empty",
        ):
            ApplicationPresentationCorrespondenceAnchor("   ")

    def test_app_subpackages_expose_canonical_contracts(self) -> None:
        self.assertEqual(LayoutScalingStability.ISOTROPIC.value, "isotropic")
        self.assertTrue(hasattr(ApplicationPresentation, "__dataclass_fields__"))
        self.assertTrue(hasattr(ApplicationPresentationRaster, "__dataclass_fields__"))


if __name__ == "__main__":
    unittest.main()
