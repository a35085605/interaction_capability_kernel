from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypeAlias

from app.raster.identity import ApplicationRasterId
from app.presentation import (
    ApplicationPresentation,
    ApplicationPresentationCorrespondenceAnchor,
    ApplicationPresentationInCaptureUnavailable,
    ApplicationPresentationLocator,
    locate_application_presentation_in_capture,
)
from geometry import Rect
from imaging import (
    ImagePixels,
    PixelFormat,
    RasterImage,
    crop_image,
    materialize_image,
)
from capture import CapturedFrame, FrameId, FrameObservationRef


@dataclass(frozen=True, slots=True)
class ApplicationPresentationRaster:
    """Durable zero-based raster for one anchored application presentation.

    It owns contiguous storage and source-observation identity, but no geometric
    route back to the historical capture placement.
    """

    anchor: ApplicationPresentationCorrespondenceAnchor
    source_observation: FrameObservationRef
    image: RasterImage
    raster_id: ApplicationRasterId = field(init=False)
    bounds: Rect = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(
            self.anchor,
            ApplicationPresentationCorrespondenceAnchor,
        ):
            raise TypeError(
                "anchor must be ApplicationPresentationCorrespondenceAnchor"
            )
        if not isinstance(self.source_observation, FrameObservationRef):
            raise TypeError("source_observation must be FrameObservationRef")
        if not isinstance(self.image, RasterImage):
            raise TypeError("application raster image must be RasterImage")
        if not self.image.is_materialized:
            raise ValueError(
                "application raster image must own independent contiguous storage"
            )

        object.__setattr__(
            self,
            "raster_id",
            ApplicationRasterId(
                source_observation=self.source_observation,
                anchor=self.anchor,
            ),
        )
        object.__setattr__(
            self,
            "bounds",
            Rect(
                x=0,
                y=0,
                width=self.image.width,
                height=self.image.height,
            ),
        )

    @property
    def pixels(self) -> ImagePixels:
        return self.image.pixels

    @property
    def pixel_format(self) -> PixelFormat:
        return self.image.pixel_format

    @property
    def frame_id(self) -> FrameId:
        return self.source_observation.frame_id

    @property
    def bounds_raster(self) -> Rect:
        return self.bounds

    @property
    def application_presentation(self) -> ApplicationPresentation:
        """Expose the full raster as an anchored application presentation."""

        return ApplicationPresentation(
            anchor=self.anchor,
            bounds=self.bounds,
        )


ApplicationPresentationRasterExtractionResult: TypeAlias = (
    ApplicationPresentationRaster | ApplicationPresentationInCaptureUnavailable
)


def extract_application_presentation_raster(
    capture: CapturedFrame,
    *,
    anchor: ApplicationPresentationCorrespondenceAnchor,
    locator: ApplicationPresentationLocator[CapturedFrame],
) -> ApplicationPresentationRasterExtractionResult:
    """Locate and materialize an anchored application presentation as a durable raster.

    The result preserves source-observation identity and the presentation-
    correspondence assertion, not historical capture placement or locator provenance.
    """

    located = locate_application_presentation_in_capture(
        capture,
        anchor=anchor,
        locator=locator,
    )
    if isinstance(located, ApplicationPresentationInCaptureUnavailable):
        return located

    bounds_capture = located.presentation.bounds_capture
    capture_bounds = Rect(
        x=0,
        y=0,
        width=capture.info.size.width,
        height=capture.info.size.height,
    )
    image = capture.image
    if bounds_capture != capture_bounds:
        image = crop_image(image, bounds=bounds_capture)

    return ApplicationPresentationRaster(
        anchor=anchor,
        source_observation=FrameObservationRef.from_info(capture.info),
        image=materialize_image(image),
    )


__all__ = [
    "ApplicationPresentationRaster",
    "ApplicationPresentationRasterExtractionResult",
    "extract_application_presentation_raster",
]
