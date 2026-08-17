from __future__ import annotations

import unittest
from datetime import datetime, timezone

import numpy as np

from geometry import Rect, Size
from imaging import PixelFormat, RasterImage, crop_image
from capture import (
    AcquiredFrame,
    BackendFrameSource,
    CapturedFrame,
    CaptureBackendProfile,
    CaptureQuality,
    CaptureStreamId,
    FrameId,
    FrameInfo,
    MaterializingFrameSource,
    materialize_captured_frame,
)


class _Backend:
    def __init__(self, frame: AcquiredFrame) -> None:
        self._frame = frame
        self._profile = CaptureBackendProfile(backend_id="test.capture")

    @property
    def profile(self) -> CaptureBackendProfile:
        return self._profile

    def acquire(self) -> AcquiredFrame:
        return self._frame


def _acquired_frame() -> AcquiredFrame:
    backing = RasterImage(
        pixels=np.arange(6 * 7, dtype=np.uint8).reshape(6, 7),
        pixel_format=PixelFormat.GRAY8,
    )
    image = crop_image(
        backing,
        bounds=Rect(x=1, y=1, width=5, height=4),
    )
    assert not image.is_materialized
    return AcquiredFrame(
        info=FrameInfo(
            frame_id=FrameId(7),
            stream_id=CaptureStreamId("stream-1"),
            captured_at=datetime(2026, 8, 10, tzinfo=timezone.utc),
            size=Size(width=5, height=4),
            capture_backend_id="test.capture",
        ),
        image=image,
        quality=CaptureQuality(usable=True),
    )


class CaptureMaterializationBoundaryTests(unittest.TestCase):
    def test_default_source_does_not_materialize_full_frame(self) -> None:
        acquired = _acquired_frame()

        captured = BackendFrameSource(_Backend(acquired)).capture()

        self.assertIsInstance(captured, CapturedFrame)
        assert isinstance(captured, CapturedFrame)
        self.assertIs(captured.image, acquired.image)
        self.assertFalse(captured.image.is_materialized)

    def test_full_frame_materialization_is_explicit(self) -> None:
        acquired = _acquired_frame()
        captured = BackendFrameSource(_Backend(acquired)).capture()
        assert isinstance(captured, CapturedFrame)

        materialized = materialize_captured_frame(captured)

        self.assertTrue(materialized.image.is_materialized)
        self.assertEqual(materialized.info, captured.info)
        self.assertEqual(materialized.quality, captured.quality)
        self.assertFalse(np.shares_memory(materialized.pixels, captured.pixels))

    def test_materializing_source_remains_available_as_opt_in(self) -> None:
        acquired = _acquired_frame()

        captured = MaterializingFrameSource(_Backend(acquired)).capture()

        self.assertIsInstance(captured, CapturedFrame)
        assert isinstance(captured, CapturedFrame)
        self.assertTrue(captured.image.is_materialized)
        self.assertFalse(np.shares_memory(captured.pixels, acquired.image.pixels))


if __name__ == "__main__":
    unittest.main()
