from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TypeAlias

from app.presentation.anchor import ApplicationPresentationCorrespondenceAnchor
from app.presentation.location import (
    ApplicationPresentationLocationFailureReason,
    ApplicationPresentationLocationProvenance,
    ApplicationPresentationLocationUnavailable,
    ApplicationPresentationLocator,
    LocatedApplicationPresentation,
    LocatedApplicationPresentationInSurface,
)
from app.presentation.model import ApplicationPresentation
from geometry import Rect
from capture import CapturedFrame, FrameId, FrameInfo


def _normalize_optional_text(
    value: object,
    *,
    field_name: str,
) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(
            f"{field_name} must be a string, got {type(value).__name__}"
        )
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} cannot be empty")
    return normalized


def _frame_bounds(info: FrameInfo) -> Rect:
    return Rect(x=0, y=0, width=info.size.width, height=info.size.height)


class ApplicationPresentationInCaptureFailureReason(str, Enum):
    FRAME_UNUSABLE = "frame_unusable"
    PRESENTATION_NOT_LOCATED = "presentation_not_located"
    BOUNDS_OUTSIDE_CAPTURE = "bounds_outside_capture"


@dataclass(frozen=True, slots=True)
class ApplicationPresentationInCapture:
    """Historical application presentation situated in one captured-frame observation.

    ``presentation`` carries application-output presentation geometry. ``capture`` owns
    the historical observation identity and the numeric frame context in which the
    presentation bounds are interpreted. No second capture-space identity is created.
    """

    capture: FrameInfo
    presentation: ApplicationPresentation

    def __post_init__(self) -> None:
        if not isinstance(self.capture, FrameInfo):
            raise TypeError("capture must be FrameInfo")
        if not isinstance(self.presentation, ApplicationPresentation):
            raise TypeError("presentation must be ApplicationPresentation")
        capture_bounds = _frame_bounds(self.capture)
        if not capture_bounds.contains_rect(self.presentation.bounds):
            raise ValueError(
                "application presentation bounds must be contained by capture bounds"
            )

    @property
    def bounds(self) -> Rect:
        return self.presentation.bounds

    @property
    def bounds_capture(self) -> Rect:
        return self.presentation.bounds


@dataclass(frozen=True, slots=True)
class LocatedApplicationPresentationInCapture:
    presentation: ApplicationPresentationInCapture
    provenance: ApplicationPresentationLocationProvenance
    confidence: float = 1.0

    def __post_init__(self) -> None:
        if not isinstance(self.presentation, ApplicationPresentationInCapture):
            raise TypeError("presentation must be ApplicationPresentationInCapture")
        located = LocatedApplicationPresentation(
            presentation=self.presentation.presentation,
            provenance=self.provenance,
            confidence=self.confidence,
        )
        object.__setattr__(self, "confidence", located.confidence)

    @property
    def frame_id(self) -> FrameId:
        return self.presentation.capture.frame_id

    @property
    def bounds(self) -> Rect:
        return self.presentation.bounds

    @property
    def located(self) -> LocatedApplicationPresentation:
        return LocatedApplicationPresentation(
            presentation=self.presentation.presentation,
            provenance=self.provenance,
            confidence=self.confidence,
        )


@dataclass(frozen=True, slots=True)
class ApplicationPresentationInCaptureUnavailable:
    frame_id: FrameId
    reason: ApplicationPresentationInCaptureFailureReason
    detail: str | None = None
    location_reason: ApplicationPresentationLocationFailureReason | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.frame_id, FrameId):
            raise TypeError("frame_id must be FrameId")
        if not isinstance(self.reason, ApplicationPresentationInCaptureFailureReason):
            raise TypeError(
                "reason must be ApplicationPresentationInCaptureFailureReason"
            )
        if self.location_reason is not None and not isinstance(
            self.location_reason,
            ApplicationPresentationLocationFailureReason,
        ):
            raise TypeError(
                "location_reason must be "
                "ApplicationPresentationLocationFailureReason or None"
            )
        if (
            self.reason
            is ApplicationPresentationInCaptureFailureReason.PRESENTATION_NOT_LOCATED
        ):
            if self.location_reason is None:
                raise ValueError("presentation_not_located requires location_reason")
        elif self.location_reason is not None:
            raise ValueError(
                "location_reason is only valid for presentation_not_located"
            )
        object.__setattr__(
            self,
            "detail",
            _normalize_optional_text(
                self.detail,
                field_name="application presentation failure detail",
            ),
        )


ApplicationPresentationInCaptureResult: TypeAlias = (
    LocatedApplicationPresentationInCapture | ApplicationPresentationInCaptureUnavailable
)


def locate_application_presentation_in_capture(
    capture: CapturedFrame,
    *,
    anchor: ApplicationPresentationCorrespondenceAnchor,
    locator: ApplicationPresentationLocator[CapturedFrame],
) -> ApplicationPresentationInCaptureResult:
    """Locate and anchor one application presentation in a captured-frame surface."""

    if not isinstance(capture, CapturedFrame):
        raise TypeError("capture must be CapturedFrame")
    if not isinstance(anchor, ApplicationPresentationCorrespondenceAnchor):
        raise TypeError(
            "anchor must be ApplicationPresentationCorrespondenceAnchor"
        )
    if not hasattr(locator, "locate"):
        raise TypeError("locator must provide locate()")

    if not capture.quality.usable:
        return ApplicationPresentationInCaptureUnavailable(
            frame_id=capture.info.frame_id,
            reason=ApplicationPresentationInCaptureFailureReason.FRAME_UNUSABLE,
        )

    located = locator.locate(capture)
    if isinstance(located, ApplicationPresentationLocationUnavailable):
        return ApplicationPresentationInCaptureUnavailable(
            frame_id=capture.info.frame_id,
            reason=ApplicationPresentationInCaptureFailureReason.PRESENTATION_NOT_LOCATED,
            detail=located.detail,
            location_reason=located.reason,
        )
    if not isinstance(located, LocatedApplicationPresentationInSurface):
        raise TypeError(
            "application presentation locator must return "
            "LocatedApplicationPresentationInSurface or "
            "ApplicationPresentationLocationUnavailable"
        )
    if located.surface is not capture:
        raise ValueError("locator result must belong to the supplied capture surface")

    capture_bounds = _frame_bounds(capture.info)
    if not capture_bounds.contains_rect(located.bounds):
        return ApplicationPresentationInCaptureUnavailable(
            frame_id=capture.info.frame_id,
            reason=ApplicationPresentationInCaptureFailureReason.BOUNDS_OUTSIDE_CAPTURE,
            detail=(
                f"application presentation bounds {located.bounds} are outside "
                f"capture bounds {capture_bounds}"
            ),
        )

    return LocatedApplicationPresentationInCapture(
        presentation=ApplicationPresentationInCapture(
            capture=capture.info,
            presentation=ApplicationPresentation(
                anchor=anchor,
                bounds=located.bounds,
            ),
        ),
        provenance=located.provenance,
        confidence=located.confidence,
    )


__all__ = [
    "ApplicationPresentationInCapture",
    "ApplicationPresentationInCaptureFailureReason",
    "ApplicationPresentationInCaptureResult",
    "ApplicationPresentationInCaptureUnavailable",
    "LocatedApplicationPresentationInCapture",
    "locate_application_presentation_in_capture",
]
