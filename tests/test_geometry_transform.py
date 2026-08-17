from __future__ import annotations

import unittest

from geometry import AxisAlignedTransform, Rect


class AxisAlignedTransformTests(unittest.TestCase):
    def test_identity_preserves_coordinates_and_rects(self) -> None:
        transform = AxisAlignedTransform.identity()
        rect = Rect(x=10, y=20, width=30, height=40)

        self.assertEqual(transform.map_xy(12, 34), (12.0, 34.0))
        self.assertEqual(transform.map_rect_exact(rect), rect)

    def test_from_rects_maps_source_bounds_to_target_bounds(self) -> None:
        source = Rect(x=10, y=20, width=100, height=50)
        target = Rect(x=100, y=200, width=200, height=150)

        transform = AxisAlignedTransform.from_rects(source, target)

        self.assertEqual(transform.scale_x, 2.0)
        self.assertEqual(transform.scale_y, 3.0)
        self.assertEqual(transform.offset_x, 80.0)
        self.assertEqual(transform.offset_y, 140.0)
        self.assertEqual(transform.map_rect_exact(source), target)

    def test_map_rect_exact_rejects_fractional_edges(self) -> None:
        transform = AxisAlignedTransform(scale_x=0.5, scale_y=0.5)

        with self.assertRaisesRegex(ValueError, "must be integer coordinates"):
            transform.map_rect_exact(Rect(x=1, y=1, width=2, height=2))

    def test_map_rect_enclosing_contains_fractional_mapping(self) -> None:
        transform = AxisAlignedTransform(
            scale_x=0.5,
            scale_y=0.5,
            offset_x=0.25,
            offset_y=0.25,
        )

        mapped = transform.map_rect_enclosing(
            Rect(x=1, y=1, width=3, height=3)
        )

        self.assertEqual(mapped, Rect(x=0, y=0, width=3, height=3))

    def test_inverse_round_trips_coordinates(self) -> None:
        transform = AxisAlignedTransform(
            scale_x=2.0,
            scale_y=3.0,
            offset_x=10.0,
            offset_y=-4.0,
        )
        inverse = transform.inverse()

        mapped = transform.map_xy(7, 11)

        self.assertEqual(inverse.map_xy(*mapped), (7.0, 11.0))

    def test_then_matches_sequential_mapping(self) -> None:
        inner = AxisAlignedTransform(
            scale_x=2.0,
            scale_y=3.0,
            offset_x=5.0,
            offset_y=7.0,
        )
        outer = AxisAlignedTransform(
            scale_x=0.5,
            scale_y=4.0,
            offset_x=-2.0,
            offset_y=1.0,
        )

        composed = inner.then(outer)
        inner_xy = inner.map_xy(10, 20)

        self.assertEqual(composed.map_xy(10, 20), outer.map_xy(*inner_xy))


if __name__ == "__main__":
    unittest.main()
