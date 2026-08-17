from __future__ import annotations

import math
import unittest

from app.presentation import (
    ApplicationPresentation,
    ApplicationPresentationCorrespondenceAnchor,
    ApplicationPresentationMapping,
)
from geometry import AxisAlignedTransform, LocalPlacement, Point, Rect


class PointTests(unittest.TestCase):
    def test_point_normalizes_real_values_to_floats(self) -> None:
        point = Point(x=1, y=2.5)

        self.assertEqual(point.as_tuple(), (1.0, 2.5))
        self.assertIsInstance(point.x, float)
        self.assertIsInstance(point.y, float)

    def test_point_rejects_non_finite_values_and_bool(self) -> None:
        with self.assertRaises(TypeError):
            Point(x=True, y=0)
        with self.assertRaises(ValueError):
            Point(x=math.inf, y=0)
        with self.assertRaises(ValueError):
            Point(x=0, y=math.nan)

    def test_point_translation_preserves_fractional_coordinates(self) -> None:
        self.assertEqual(
            Point(x=1.25, y=2.5).translated(dx=0.5, dy=-1.25),
            Point(x=1.75, y=1.25),
        )


class RectPointTests(unittest.TestCase):
    def test_center_is_continuous_point(self) -> None:
        rect = Rect(x=10, y=20, width=3, height=5)

        self.assertEqual(rect.center, Point(x=11.5, y=22.5))

    def test_contains_point_accepts_fractional_coordinates(self) -> None:
        rect = Rect(x=10, y=20, width=3, height=5)

        self.assertTrue(rect.contains_point(Point(x=12.999, y=24.999)))
        self.assertFalse(rect.contains_point(Point(x=13, y=24)))
        self.assertFalse(rect.contains_point(Point(x=12, y=25)))


class ContinuousMappingTests(unittest.TestCase):
    def test_transform_maps_points_without_quantization(self) -> None:
        transform = AxisAlignedTransform(
            scale_x=1.5,
            scale_y=2.0,
            offset_x=0.25,
            offset_y=-0.5,
        )

        mapped = transform.map_point(Point(x=2.5, y=3.25))

        self.assertEqual(mapped, Point(x=4.0, y=6.0))
        self.assertEqual(transform.inverse_point(mapped), Point(x=2.5, y=3.25))

    def test_local_placement_preserves_fractional_point(self) -> None:
        placement = LocalPlacement.from_rects(
            local_bounds=Rect(x=0, y=0, width=20, height=10),
            bounds_root=Rect(x=100, y=50, width=40, height=20),
        )

        self.assertEqual(
            placement.map_point_to_root(Point(x=5.25, y=5.25)),
            Point(x=110.5, y=60.5),
        )

    def test_application_presentation_mapping_preserves_fractional_point(self) -> None:
        anchor = ApplicationPresentationCorrespondenceAnchor("continuous-point")
        mapping = ApplicationPresentationMapping(
            source=ApplicationPresentation(
                anchor=anchor,
                bounds=Rect(x=0, y=0, width=1280, height=720),
            ),
            target=ApplicationPresentation(
                anchor=anchor,
                bounds=Rect(x=100, y=200, width=1920, height=1080),
            ),
        )

        self.assertEqual(
            mapping.map_point(Point(x=640.25, y=360.5)),
            Point(x=1060.375, y=740.75),
        )


if __name__ == "__main__":
    unittest.main()
