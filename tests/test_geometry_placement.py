from __future__ import annotations

from dataclasses import fields
import unittest

from geometry import AxisAlignedTransform, LocalPlacement, Point, Rect


class LocalPlacementTests(unittest.TestCase):
    def test_local_placement_maps_directly_to_domain_root(self) -> None:
        placement = LocalPlacement(
            local_bounds=Rect(x=0, y=0, width=20, height=10),
            bounds_root=Rect(x=100, y=50, width=40, height=20),
        )

        self.assertEqual(
            placement.map_point_to_root(Point(x=5, y=5)),
            Point(x=110, y=60),
        )
        self.assertEqual(
            placement.map_rect_to_root(Rect(x=2, y=2, width=5, height=3)),
            Rect(x=104, y=54, width=10, height=6),
        )

    def test_local_placement_derives_transform_from_bounds(self) -> None:
        local_bounds = Rect(x=0, y=0, width=10, height=10)
        bounds_root = Rect(x=50, y=75, width=10, height=10)
        placement = LocalPlacement(
            local_bounds=local_bounds,
            bounds_root=bounds_root,
        )

        self.assertEqual(
            tuple(field.name for field in fields(LocalPlacement)),
            ("local_bounds", "bounds_root"),
        )
        self.assertEqual(
            placement.local_to_root,
            AxisAlignedTransform.from_rects(local_bounds, bounds_root),
        )
        self.assertEqual(
            LocalPlacement.from_rects(
                local_bounds=local_bounds,
                bounds_root=bounds_root,
            ),
            placement,
        )

    def test_local_placement_owns_math_not_identity(self) -> None:
        placement = LocalPlacement(
            local_bounds=Rect(x=0, y=0, width=10, height=10),
            bounds_root=Rect(x=50, y=75, width=10, height=10),
        )

        self.assertFalse(hasattr(placement, "root_space_id"))
        self.assertFalse(hasattr(placement, "child_space_id"))


if __name__ == "__main__":
    unittest.main()
