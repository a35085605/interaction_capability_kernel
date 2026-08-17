from __future__ import annotations

import unittest

import cv2
import numpy as np

from adb.errors import AdbTransportNotFoundError
from adb.server import AdbServerEndpoint
from adb.transport import AdbDeviceSerial, AdbTransportBySerial
from android.display import AndroidDisplayId, AndroidPhysicalDisplayId
from capture import AcquiredFrame, CaptureUnavailable, CaptureUnavailableReason
from capture.adapters.android_adb import AdbScreencapBackend, AndroidAdbCaptureSource
from imaging import PixelFormat


class _FakeClient:
    def __init__(self, payload: bytes = b"") -> None:
        self.payload = payload
        self.calls: list[tuple[object, str]] = []
        self.error: Exception | None = None

    def raw_exec(self, selector, command: str) -> bytes:
        self.calls.append((selector, command))
        if self.error is not None:
            raise self.error
        return self.payload


class AdbScreencapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.endpoint = AdbServerEndpoint()
        self.selector = AdbTransportBySerial(AdbDeviceSerial("device-1"))
        self.display_id = AndroidPhysicalDisplayId(4619827259835644672)

    def _backend(self, fake: _FakeClient) -> AdbScreencapBackend:
        return AdbScreencapBackend(
            self.endpoint,
            self.selector,
            self.display_id,
            _client_factory=lambda endpoint: fake,
        )

    def test_explicit_physical_display_png_becomes_acquired_frame(self) -> None:
        source = np.zeros((2, 3, 3), dtype=np.uint8)
        source[0, 0] = (1, 2, 3)
        ok, encoded = cv2.imencode(".png", source)
        self.assertTrue(ok)
        fake = _FakeClient(bytes(encoded))
        backend = self._backend(fake)

        first = backend.acquire()
        second = backend.acquire()

        self.assertIsInstance(first, AcquiredFrame)
        self.assertIsInstance(second, AcquiredFrame)
        assert isinstance(first, AcquiredFrame)
        assert isinstance(second, AcquiredFrame)
        self.assertEqual(first.info.size.width, 3)
        self.assertEqual(first.info.size.height, 2)
        self.assertEqual(first.image.pixel_format, PixelFormat.BGR24)
        self.assertEqual(first.info.frame_id.value, 0)
        self.assertEqual(second.info.frame_id.value, 1)
        self.assertEqual(first.info.stream_id, second.info.stream_id)
        self.assertEqual(first.info.source_id, backend.source.source_id)
        self.assertIsInstance(backend.source, AndroidAdbCaptureSource)
        self.assertEqual(backend.source.physical_display_id, self.display_id)
        self.assertIsNone(backend.source.logical_display_id)
        self.assertEqual(
            fake.calls,
            [(self.selector, "screencap -p -d 4619827259835644672")] * 2,
        )

    def test_explicit_logical_display_correspondence_is_preserved_without_inference(self) -> None:
        fake = _FakeClient()
        backend = AdbScreencapBackend(
            self.endpoint, self.selector, self.display_id,
            logical_display_id=AndroidDisplayId(7),
            _client_factory=lambda endpoint: fake,
        )

        self.assertEqual(backend.source.logical_display_id, AndroidDisplayId(7))
        self.assertEqual(backend.source.physical_display_id, self.display_id)

    def test_logical_display_id_cannot_be_used_as_capture_identity(self) -> None:
        with self.assertRaisesRegex(TypeError, "AndroidPhysicalDisplayId"):
            AdbScreencapBackend(
                self.endpoint,
                self.selector,
                AndroidDisplayId(0),  # type: ignore[arg-type]
            )

    def test_transport_selection_failure_is_source_unavailable(self) -> None:
        fake = _FakeClient()
        fake.error = AdbTransportNotFoundError(
            "host:transport:missing",
            "device not found",
        )
        backend = self._backend(fake)

        result = backend.acquire()

        self.assertIsInstance(result, CaptureUnavailable)
        assert isinstance(result, CaptureUnavailable)
        self.assertIs(result.reason, CaptureUnavailableReason.SOURCE_UNAVAILABLE)

    def test_invalid_image_payload_is_transient_failure(self) -> None:
        fake = _FakeClient(b"not-a-png")
        backend = self._backend(fake)

        result = backend.acquire()

        self.assertIsInstance(result, CaptureUnavailable)
        assert isinstance(result, CaptureUnavailable)
        self.assertIs(result.reason, CaptureUnavailableReason.TRANSIENT_FAILURE)


if __name__ == "__main__":
    unittest.main()
