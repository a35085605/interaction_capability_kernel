from __future__ import annotations

import unittest

import app.layout
from app.layout import LayoutScalingStability


class LayoutScalingStabilityTests(unittest.TestCase):
    def test_public_surface_is_scaling_stability_only(self) -> None:
        self.assertEqual(app.layout.__all__, ["LayoutScalingStability"])

    def test_public_values_are_minimal_and_stable(self) -> None:
        self.assertEqual(
            list(LayoutScalingStability),
            [
                LayoutScalingStability.UNSTABLE,
                LayoutScalingStability.ISOTROPIC,
                LayoutScalingStability.ANISOTROPIC,
            ],
        )
        self.assertEqual(LayoutScalingStability.UNSTABLE.value, "unstable")
        self.assertEqual(LayoutScalingStability.ISOTROPIC.value, "isotropic")
        self.assertEqual(LayoutScalingStability.ANISOTROPIC.value, "anisotropic")


if __name__ == "__main__":
    unittest.main()
