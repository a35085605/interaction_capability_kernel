from __future__ import annotations

from dataclasses import dataclass

from capture.domain.models import (
    CaptureStreamId,
    FrameId,
    FrameInfo,
)


@dataclass(frozen=True, slots=True)
class FrameObservationRef:
    """Stream-scoped identity of one captured-frame observation."""

    stream_id: CaptureStreamId
    frame_id: FrameId

    def __post_init__(self) -> None:
        if not isinstance(self.stream_id, CaptureStreamId):
            raise TypeError("stream_id must be CaptureStreamId")
        if not isinstance(self.frame_id, FrameId):
            raise TypeError("frame_id must be FrameId")

    @classmethod
    def from_info(cls, info: FrameInfo) -> FrameObservationRef:
        if not isinstance(info, FrameInfo):
            raise TypeError("info must be FrameInfo")
        return cls(
            stream_id=info.stream_id,
            frame_id=info.frame_id,
        )


__all__ = ["FrameObservationRef"]
