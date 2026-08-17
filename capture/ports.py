from __future__ import annotations

from typing import Protocol, TypeAlias

from capture.domain.models import AcquiredFrame, CapturedFrame
from capture.domain.backend import (
    CaptureBackendProfile,
    CaptureUnavailable,
)


AcquiredFrameResult: TypeAlias = AcquiredFrame | CaptureUnavailable
CapturedFrameResult: TypeAlias = CapturedFrame | CaptureUnavailable


class FrameCaptureBackend(Protocol):
    """Platform-facing port for one read-only visual acquisition attempt.

    Expected blockers are returned as ``CaptureUnavailable``; external composition owns
    preparation, retry, waiting, and fallback.
    """

    @property
    def profile(self) -> CaptureBackendProfile:
        """Expose the capture backend identity."""
        ...

    def acquire(self) -> AcquiredFrameResult:
        """Acquire one backend frame or describe why it is unavailable."""
        ...


class CapturedFrameSource(Protocol):
    """Application-facing source of immutable logical capture results.

    Successful frames need not own contiguous storage, and capture success does
    not imply that the interaction target is currently controllable.
    """

    @property
    def profile(self) -> CaptureBackendProfile:
        """Expose the underlying capture backend profile."""
        ...

    def capture(self) -> CapturedFrameResult:
        """Return one frame observation or a typed unavailable result."""
        ...
