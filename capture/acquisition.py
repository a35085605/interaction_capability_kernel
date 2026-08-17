from __future__ import annotations

from dataclasses import dataclass

from imaging import materialize_image
from capture.domain.models import AcquiredFrame, CapturedFrame
from capture.domain.backend import (
    CaptureBackendProfile,
    CaptureUnavailable,
)
from capture.ports import CapturedFrameResult, FrameCaptureBackend


def captured_frame_from_acquired(frame: AcquiredFrame) -> CapturedFrame:
    """Cross the capture boundary without forcing full-frame materialization."""

    if not isinstance(frame, AcquiredFrame):
        raise TypeError("frame must be AcquiredFrame")

    return CapturedFrame(
        info=frame.info,
        image=frame.image,
        quality=frame.quality,
    )


def materialize_captured_frame(frame: CapturedFrame) -> CapturedFrame:
    """Return the same observation with independent contiguous pixel storage.

    Full-frame materialization is optional at the Capture boundary. Callers may
    use this helper for debugging, archival, or another consumer that explicitly
    requires an independently owned contiguous raster.
    """

    if not isinstance(frame, CapturedFrame):
        raise TypeError("frame must be CapturedFrame")

    return CapturedFrame(
        info=frame.info,
        image=materialize_image(frame.image),
        quality=frame.quality,
    )


def materialize_acquired_frame(frame: AcquiredFrame) -> CapturedFrame:
    """Cross the capture boundary and explicitly materialize the full raster."""

    return materialize_captured_frame(captured_frame_from_acquired(frame))


def _validate_unavailable(
    unavailable: CaptureUnavailable,
    *,
    profile: CaptureBackendProfile,
) -> None:
    if unavailable.backend_id != profile.backend_id:
        raise ValueError(
            "capture unavailable backend_id must match backend profile"
        )


def _validate_backend(backend: FrameCaptureBackend) -> None:
    if not hasattr(backend, "profile"):
        raise TypeError("backend must provide profile")
    if not hasattr(backend, "acquire"):
        raise TypeError("backend must provide acquire()")
    if not isinstance(backend.profile, CaptureBackendProfile):
        raise TypeError("backend profile must be CaptureBackendProfile")


def _acquire(backend: FrameCaptureBackend) -> AcquiredFrame | CaptureUnavailable:
    acquired = backend.acquire()
    if isinstance(acquired, CaptureUnavailable):
        _validate_unavailable(acquired, profile=backend.profile)
        return acquired
    if not isinstance(acquired, AcquiredFrame):
        raise TypeError(
            "frame capture backend must return AcquiredFrame "
            "or CaptureUnavailable"
        )
    return acquired


@dataclass(frozen=True, slots=True)
class BackendFrameSource:
    """Application-facing capture source without eager raster materialization."""

    backend: FrameCaptureBackend

    def __post_init__(self) -> None:
        _validate_backend(self.backend)

    @property
    def profile(self) -> CaptureBackendProfile:
        return self.backend.profile

    def capture(self) -> CapturedFrameResult:
        acquired = _acquire(self.backend)
        if isinstance(acquired, CaptureUnavailable):
            return acquired
        return captured_frame_from_acquired(acquired)


@dataclass(frozen=True, slots=True)
class MaterializingFrameSource:
    """Opt-in source that materializes every successful full-frame capture.

    Prefer ``BackendFrameSource`` when downstream consumers materialize only the
    content or debug raster they actually need.
    """

    backend: FrameCaptureBackend

    def __post_init__(self) -> None:
        _validate_backend(self.backend)

    @property
    def profile(self) -> CaptureBackendProfile:
        return self.backend.profile

    def capture(self) -> CapturedFrameResult:
        acquired = _acquire(self.backend)
        if isinstance(acquired, CaptureUnavailable):
            return acquired
        return materialize_acquired_frame(acquired)
