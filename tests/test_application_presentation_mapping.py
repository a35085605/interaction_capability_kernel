from __future__ import annotations

import unittest

from app.presentation import (
    ApplicationPresentation,
    ApplicationPresentationCorrespondenceAnchor,
    ApplicationPresentationMapping,
)
from geometry import Point, Rect


class ApplicationPresentationMappingTests(unittest.TestCase):
    def test_mapping_is_constructed_from_corresponding_presentations(self) -> None:
        anchor = ApplicationPresentationCorrespondenceAnchor(
            "primary-presentation-correspondence"
        )
        source = ApplicationPresentation(
            anchor=anchor,
            bounds=Rect(x=0, y=0, width=1280, height=720),
        )
        target = ApplicationPresentation(
            anchor=anchor,
            bounds=Rect(x=100, y=200, width=1920, height=1080),
        )

        mapping = ApplicationPresentationMapping(source=source, target=target)

        self.assertEqual(mapping.map_point(Point(x=640, y=360)), Point(x=1060, y=740))
        self.assertEqual(
            mapping.map_rect(Rect(x=0, y=0, width=1280, height=720)),
            target.bounds,
        )

    def test_mapping_allows_identical_projection_geometry(self) -> None:
        anchor = ApplicationPresentationCorrespondenceAnchor(
            "primary-presentation-correspondence"
        )
        source = ApplicationPresentation(
            anchor=anchor,
            bounds=Rect(x=100, y=100, width=300, height=400),
        )
        target = ApplicationPresentation(
            anchor=anchor,
            bounds=Rect(x=100, y=100, width=300, height=400),
        )

        mapping = ApplicationPresentationMapping(source=source, target=target)

        self.assertEqual(mapping.map_point(Point(x=150, y=200)), Point(x=150, y=200))

    def test_mapping_rejects_different_correspondence_anchors(self) -> None:
        source = ApplicationPresentation(
            anchor=ApplicationPresentationCorrespondenceAnchor("correspondence-a"),
            bounds=Rect(x=0, y=0, width=100, height=100),
        )
        target = ApplicationPresentation(
            anchor=ApplicationPresentationCorrespondenceAnchor("correspondence-b"),
            bounds=Rect(x=0, y=0, width=100, height=100),
        )

        with self.assertRaisesRegex(
            ValueError,
            "requires the same correspondence anchor",
        ):
            ApplicationPresentationMapping(source=source, target=target)


if __name__ == "__main__":
    unittest.main()
