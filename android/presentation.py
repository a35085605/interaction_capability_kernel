from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TypeAlias

from android.display import AndroidDisplayId
from android.spatial import AndroidDisplaySurface
from app.presentation import (
    ApplicationPresentation,
    ApplicationPresentationCorrespondenceAnchor,
    ApplicationPresentationLocationFailureReason,
    ApplicationPresentationLocationProvenance,
    ApplicationPresentationLocationUnavailable,
    ApplicationPresentationLocator,
    LocatedApplicationPresentation,
    LocatedApplicationPresentationInSurface,
)
from geometry import Rect


class ApplicationPresentationInAndroidDisplayFailureReason(str, Enum):
    PRESENTATION_NOT_LOCATED = "presentation_not_located"
    BOUNDS_OUTSIDE_DISPLAY = "bounds_outside_display"


@dataclass(frozen=True, slots=True)
class ApplicationPresentationInAndroidDisplay:
    """Application presentation interpreted in one Android display surface."""

    surface: AndroidDisplaySurface
    presentation: ApplicationPresentation

    def __post_init__(self) -> None:
        if not isinstance(self.surface, AndroidDisplaySurface):
            raise TypeError("surface must be AndroidDisplaySurface")
        if not isinstance(self.presentation, ApplicationPresentation):
            raise TypeError("presentation must be ApplicationPresentation")
        if not self.surface.bounds.contains_rect(self.presentation.bounds):
            raise ValueError(
                "application presentation bounds must be contained by Android display bounds"
            )

    @property
    def display_id(self) -> AndroidDisplayId:
        return self.surface.display_id

    @property
    def bounds(self) -> Rect:
        return self.presentation.bounds

    @property
    def bounds_display(self) -> Rect:
        return self.presentation.bounds


@dataclass(frozen=True, slots=True)
class LocatedApplicationPresentationInAndroidDisplay:
    presentation: ApplicationPresentationInAndroidDisplay
    provenance: ApplicationPresentationLocationProvenance
    confidence: float = 1.0

    def __post_init__(self) -> None:
        if not isinstance(self.presentation, ApplicationPresentationInAndroidDisplay):
            raise TypeError("presentation must be ApplicationPresentationInAndroidDisplay")
        located = LocatedApplicationPresentation(
            presentation=self.presentation.presentation,
            provenance=self.provenance,
            confidence=self.confidence,
        )
        object.__setattr__(self, "confidence", located.confidence)


@dataclass(frozen=True, slots=True)
class ApplicationPresentationInAndroidDisplayUnavailable:
    display_id: AndroidDisplayId
    reason: ApplicationPresentationInAndroidDisplayFailureReason
    detail: str | None = None
    location_reason: ApplicationPresentationLocationFailureReason | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.display_id, AndroidDisplayId):
            raise TypeError("display_id must be AndroidDisplayId")
        if not isinstance(
            self.reason,
            ApplicationPresentationInAndroidDisplayFailureReason,
        ):
            raise TypeError(
                "reason must be ApplicationPresentationInAndroidDisplayFailureReason"
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
            is ApplicationPresentationInAndroidDisplayFailureReason.PRESENTATION_NOT_LOCATED
        ):
            if self.location_reason is None:
                raise ValueError("presentation_not_located requires location_reason")
        elif self.location_reason is not None:
            raise ValueError(
                "location_reason is only valid for presentation_not_located"
            )
        if self.detail is not None:
            if not isinstance(self.detail, str):
                raise TypeError("application presentation failure detail must be a string")
            detail = self.detail.strip()
            if not detail:
                raise ValueError("application presentation failure detail cannot be empty")
            object.__setattr__(self, "detail", detail)


ApplicationPresentationInAndroidDisplayResult: TypeAlias = (
    LocatedApplicationPresentationInAndroidDisplay
    | ApplicationPresentationInAndroidDisplayUnavailable
)


def locate_application_presentation_in_android_display(
    surface: AndroidDisplaySurface,
    *,
    anchor: ApplicationPresentationCorrespondenceAnchor,
    locator: ApplicationPresentationLocator[AndroidDisplaySurface],
) -> ApplicationPresentationInAndroidDisplayResult:
    """Locate and anchor one presentation in an Android display surface."""

    if not isinstance(surface, AndroidDisplaySurface):
        raise TypeError("surface must be AndroidDisplaySurface")
    if not isinstance(anchor, ApplicationPresentationCorrespondenceAnchor):
        raise TypeError("anchor must be ApplicationPresentationCorrespondenceAnchor")
    if not hasattr(locator, "locate"):
        raise TypeError("locator must provide locate()")

    located = locator.locate(surface)
    if isinstance(located, ApplicationPresentationLocationUnavailable):
        return ApplicationPresentationInAndroidDisplayUnavailable(
            display_id=surface.display_id,
            reason=(
                ApplicationPresentationInAndroidDisplayFailureReason.PRESENTATION_NOT_LOCATED
            ),
            detail=located.detail,
            location_reason=located.reason,
        )
    if not isinstance(located, LocatedApplicationPresentationInSurface):
        raise TypeError(
            "application presentation locator must return "
            "LocatedApplicationPresentationInSurface or "
            "ApplicationPresentationLocationUnavailable"
        )
    if located.surface is not surface:
        raise ValueError("locator result must belong to the supplied Android display surface")

    if not surface.bounds.contains_rect(located.bounds):
        return ApplicationPresentationInAndroidDisplayUnavailable(
            display_id=surface.display_id,
            reason=ApplicationPresentationInAndroidDisplayFailureReason.BOUNDS_OUTSIDE_DISPLAY,
            detail=(
                f"application presentation bounds {located.bounds} are outside "
                f"Android display bounds {surface.bounds}"
            ),
        )

    return LocatedApplicationPresentationInAndroidDisplay(
        presentation=ApplicationPresentationInAndroidDisplay(
            surface=surface,
            presentation=ApplicationPresentation(
                anchor=anchor,
                bounds=located.bounds,
            ),
        ),
        provenance=located.provenance,
        confidence=located.confidence,
    )


__all__ = [
    "ApplicationPresentationInAndroidDisplay",
    "ApplicationPresentationInAndroidDisplayFailureReason",
    "ApplicationPresentationInAndroidDisplayResult",
    "ApplicationPresentationInAndroidDisplayUnavailable",
    "LocatedApplicationPresentationInAndroidDisplay",
    "locate_application_presentation_in_android_display",
]
