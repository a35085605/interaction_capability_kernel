"""Visual capture capability contracts and acquired-frame vocabulary."""

from capture.acquisition import (
    BackendFrameSource,
    MaterializingFrameSource,
    captured_frame_from_acquired,
    materialize_acquired_frame,
    materialize_captured_frame,
)
from capture.domain.identity import FrameObservationRef
from capture.domain.source import CaptureSourceId
from capture.domain.models import (
    AcquiredFrame,
    CapturedFrame,
    CaptureQuality,
    CaptureStreamId,
    FrameId,
    FrameInfo,
)
from capture.domain.backend import (
    CaptureBackendProfile,
    CaptureUnavailable,
    CaptureUnavailableReason,
)
from capture.ports import (
    AcquiredFrameResult,
    CapturedFrameResult,
    CapturedFrameSource,
    FrameCaptureBackend,
)

__all__ = [
    "AcquiredFrame",
    "AcquiredFrameResult",
    "BackendFrameSource",
    "CapturedFrame",
    "CapturedFrameResult",
    "CapturedFrameSource",
    "CaptureBackendProfile",
    "CaptureQuality",
    "CaptureStreamId",
    "CaptureSourceId",
    "CaptureUnavailable",
    "CaptureUnavailableReason",
    "FrameCaptureBackend",
    "FrameId",
    "FrameInfo",
    "FrameObservationRef",
    "MaterializingFrameSource",
    "captured_frame_from_acquired",
    "materialize_acquired_frame",
    "materialize_captured_frame",
]
