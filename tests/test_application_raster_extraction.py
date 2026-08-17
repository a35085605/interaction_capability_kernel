from __future__ import annotations

import unittest
from datetime import datetime, timezone

import numpy as np

from app.raster import (
    ApplicationRasterId,
    ApplicationPresentationRaster,
    extract_application_presentation_raster,
)
from app.presentation import ApplicationPresentationCorrespondenceAnchor
from app.presentation.adapters import ConfiguredApplicationPresentationLocator
from geometry import Rect, Size
from imaging import PixelFormat, RasterImage, crop_image
from capture import (
    CaptureQuality,
    CapturedFrame,
    CaptureStreamId,
    FrameId,
    FrameInfo,
    FrameObservationRef,
)


class ApplicationPresentationRasterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.anchor = ApplicationPresentationCorrespondenceAnchor(
            "primary-presentation-correspondence"
        )

    def capture(self, *, materialized: bool = True) -> CapturedFrame:
        if materialized:
            image = RasterImage(
                pixels=np.arange(4 * 5, dtype=np.uint8).reshape(4, 5),
                pixel_format=PixelFormat.GRAY8,
            )
        else:
            backing = RasterImage(
                pixels=np.arange(6 * 7, dtype=np.uint8).reshape(6, 7),
                pixel_format=PixelFormat.GRAY8,
            )
            image = crop_image(
                backing,
                bounds=Rect(x=1, y=1, width=5, height=4),
            )
            self.assertFalse(image.is_materialized)

        return CapturedFrame(
            info=FrameInfo(
                frame_id=FrameId(1),
                stream_id=CaptureStreamId("stream-1"),
                captured_at=datetime(2026, 8, 10, tzinfo=timezone.utc),
                size=Size(width=5, height=4),
                capture_backend_id="test.capture",
            ),
            image=image,
            quality=CaptureQuality(usable=True),
        )

    def test_extraction_materializes_only_selected_application_raster(self) -> None:
        capture = self.capture(materialized=False)
        raster = extract_application_presentation_raster(
            capture,
            anchor=self.anchor,
            locator=ConfiguredApplicationPresentationLocator(
                bounds=Rect(x=1, y=1, width=3, height=2)
            ),
        )

        self.assertIsInstance(raster, ApplicationPresentationRaster)
        assert isinstance(raster, ApplicationPresentationRaster)
        self.assertEqual(raster.anchor, self.anchor)
        self.assertEqual(raster.application_presentation.anchor, self.anchor)
        self.assertTrue(raster.image.is_materialized)
        self.assertFalse(np.shares_memory(raster.pixels, capture.pixels))
        self.assertEqual(
            raster.source_observation,
            FrameObservationRef(
                stream_id=capture.info.stream_id,
                frame_id=capture.info.frame_id,
            ),
        )
        self.assertEqual(raster.frame_id, capture.info.frame_id)
        self.assertEqual(raster.bounds_raster, Rect(x=0, y=0, width=3, height=2))
        np.testing.assert_array_equal(
            raster.pixels,
            capture.pixels[1:3, 1:4],
        )

    def test_application_raster_uses_domain_identity(self) -> None:
        capture = self.capture()
        raster = extract_application_presentation_raster(
            capture,
            anchor=self.anchor,
            locator=ConfiguredApplicationPresentationLocator(
                bounds=Rect(x=0, y=0, width=5, height=4)
            ),
        )

        self.assertIsInstance(raster, ApplicationPresentationRaster)
        assert isinstance(raster, ApplicationPresentationRaster)
        self.assertIsInstance(raster.raster_id, ApplicationRasterId)
        self.assertEqual(raster.raster_id.source_observation, raster.source_observation)
        self.assertEqual(raster.raster_id.anchor, self.anchor)
        self.assertEqual(
            raster.raster_id.value,
            "application_raster:stream-1:1:primary-presentation-correspondence",
        )
        self.assertEqual(raster.bounds_raster, capture.image.bounds)

    def test_direct_application_raster_requires_materialized_storage(self) -> None:
        capture = self.capture(materialized=False)

        with self.assertRaisesRegex(
            ValueError,
            "application raster image must own independent contiguous storage",
        ):
            ApplicationPresentationRaster(
                anchor=self.anchor,
                source_observation=FrameObservationRef.from_info(capture.info),
                image=capture.image,
            )


if __name__ == "__main__":
    unittest.main()
