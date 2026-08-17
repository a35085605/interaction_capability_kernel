from __future__ import annotations

from dataclasses import dataclass

from app.presentation import ApplicationPresentationCorrespondenceAnchor
from capture import FrameObservationRef


@dataclass(frozen=True, slots=True)
class ApplicationRasterId:
    """Identity of one materialized application presentation raster."""

    source_observation: FrameObservationRef
    anchor: ApplicationPresentationCorrespondenceAnchor

    def __post_init__(self) -> None:
        if not isinstance(self.source_observation, FrameObservationRef):
            raise TypeError("source_observation must be FrameObservationRef")
        if not isinstance(
            self.anchor,
            ApplicationPresentationCorrespondenceAnchor,
        ):
            raise TypeError(
                "anchor must be ApplicationPresentationCorrespondenceAnchor"
            )

    @property
    def value(self) -> str:
        return (
            "application_raster:"
            f"{self.source_observation.stream_id.value}:"
            f"{self.source_observation.frame_id.value}:"
            f"{self.anchor.value}"
        )

    def __str__(self) -> str:
        return self.value


__all__ = ["ApplicationRasterId"]
