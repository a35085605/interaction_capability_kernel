from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4

import cv2
import numpy as np

from adb._internal.client import AdbServiceClient
from adb.errors import AdbError, AdbTransportSelectionError
from adb.server import AdbServerEndpoint
from adb.transport import AdbTransportSelector
from android.display import AndroidDisplayId, AndroidPhysicalDisplayId
from capture.domain.backend import CaptureBackendProfile, CaptureUnavailable, CaptureUnavailableReason
from capture.domain.models import AcquiredFrame, CaptureQuality, CaptureStreamId, FrameId, FrameInfo
from capture.domain.source import CaptureSourceId
from geometry import Size
from imaging import PixelFormat, RasterImage


_ClientFactory = Callable[[AdbServerEndpoint], AdbServiceClient]


def _default_client_factory(endpoint: AdbServerEndpoint) -> AdbServiceClient:
    return AdbServiceClient(endpoint)


@dataclass(frozen=True, slots=True)
class AndroidAdbCaptureSource:
    """Typed Android meaning for one platform-neutral capture source identity.

    ``logical_display_id`` is optional and may be supplied only when the caller has an
    independently observed logical-to-physical display relation. The backend never infers
    that relation from matching numeric IDs.
    """

    source_id: CaptureSourceId
    physical_display_id: AndroidPhysicalDisplayId
    logical_display_id: AndroidDisplayId | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, CaptureSourceId):
            raise TypeError("source_id must be CaptureSourceId")
        if not isinstance(self.physical_display_id, AndroidPhysicalDisplayId):
            raise TypeError("physical_display_id must be AndroidPhysicalDisplayId")
        if self.logical_display_id is not None and not isinstance(
            self.logical_display_id, AndroidDisplayId
        ):
            raise TypeError("logical_display_id must be AndroidDisplayId or None")


class AdbScreencapBackend:
    """Read-only PNG capture for one explicit SurfaceFlinger physical display."""

    _BACKEND_ID = "android.adb.screencap"

    def __init__(
        self,
        endpoint: AdbServerEndpoint,
        selector: AdbTransportSelector,
        display_id: AndroidPhysicalDisplayId,
        *,
        logical_display_id: AndroidDisplayId | None = None,
        _client_factory: _ClientFactory = _default_client_factory,
    ) -> None:
        if not isinstance(endpoint, AdbServerEndpoint):
            raise TypeError("endpoint must be AdbServerEndpoint")
        if not isinstance(display_id, AndroidPhysicalDisplayId):
            raise TypeError("display_id must be AndroidPhysicalDisplayId")
        if logical_display_id is not None and not isinstance(logical_display_id, AndroidDisplayId):
            raise TypeError("logical_display_id must be AndroidDisplayId or None")
        self.endpoint = endpoint
        self.selector = selector
        self.display_id = display_id
        self._client_factory = _client_factory
        self._profile = CaptureBackendProfile(backend_id=self._BACKEND_ID)
        self._source = AndroidAdbCaptureSource(
            source_id=CaptureSourceId(f"android.adb.physical-display:{display_id.value}"),
            physical_display_id=display_id,
            logical_display_id=logical_display_id,
        )
        self._stream_id = CaptureStreamId(f"{self._BACKEND_ID}:{uuid4()}")
        self._lock = Lock()
        self._next_frame_id = 0

    @property
    def profile(self) -> CaptureBackendProfile:
        return self._profile

    @property
    def source(self) -> AndroidAdbCaptureSource:
        return self._source

    def acquire(self) -> AcquiredFrame | CaptureUnavailable:
        try:
            png = self._client_factory(self.endpoint).raw_exec(
                self.selector,
                f"screencap -p -d {self.display_id.value}",
            )
        except AdbTransportSelectionError as exc:
            return CaptureUnavailable(
                backend_id=self._BACKEND_ID,
                reason=CaptureUnavailableReason.SOURCE_UNAVAILABLE,
                detail=str(exc),
            )
        except AdbError as exc:
            detail = str(exc)
            reason = (
                CaptureUnavailableReason.PERMISSION_DENIED
                if "permission" in detail.lower()
                else CaptureUnavailableReason.TRANSIENT_FAILURE
            )
            return CaptureUnavailable(backend_id=self._BACKEND_ID, reason=reason, detail=detail)

        if not png:
            return CaptureUnavailable(
                backend_id=self._BACKEND_ID,
                reason=CaptureUnavailableReason.TRANSIENT_FAILURE,
                detail="ADB screencap returned an empty payload",
            )

        pixels = cv2.imdecode(np.frombuffer(png, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
        if pixels is None:
            return CaptureUnavailable(
                backend_id=self._BACKEND_ID,
                reason=CaptureUnavailableReason.TRANSIENT_FAILURE,
                detail="ADB screencap payload is not a decodable image",
            )

        if pixels.ndim == 2:
            pixel_format = PixelFormat.GRAY8
        elif pixels.ndim == 3 and pixels.shape[2] == 3:
            pixel_format = PixelFormat.BGR24
        elif pixels.ndim == 3 and pixels.shape[2] == 4:
            pixel_format = PixelFormat.BGRA32
        else:
            return CaptureUnavailable(
                backend_id=self._BACKEND_ID,
                reason=CaptureUnavailableReason.TRANSIENT_FAILURE,
                detail=f"unsupported screencap pixel shape {pixels.shape}",
            )

        with self._lock:
            frame_id = FrameId(self._next_frame_id)
            self._next_frame_id += 1

        image = RasterImage(pixels=pixels, pixel_format=pixel_format)
        return AcquiredFrame(
            info=FrameInfo(
                frame_id=frame_id,
                stream_id=self._stream_id,
                captured_at=datetime.now(timezone.utc),
                size=Size(width=image.width, height=image.height),
                capture_backend_id=self._BACKEND_ID,
                source_id=self._source.source_id,
            ),
            image=image,
            quality=CaptureQuality(usable=True),
        )


__all__ = ["AdbScreencapBackend", "AndroidAdbCaptureSource"]
