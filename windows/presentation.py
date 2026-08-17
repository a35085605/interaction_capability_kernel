from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TypeAlias

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
from windows.identity import WindowId
from windows.spatial.window import WindowClientSurface
from windows.state import WindowState


class ApplicationPresentationInWindowFailureReason(str, Enum):
    CLIENT_SURFACE_UNAVAILABLE = "client_surface_unavailable"
    PRESENTATION_NOT_LOCATED = "presentation_not_located"
    BOUNDS_OUTSIDE_CLIENT = "bounds_outside_client"


@dataclass(frozen=True, slots=True)
class ApplicationPresentationInWindow:
    """Application presentation interpreted in one Window client-local surface."""

    surface: WindowClientSurface
    presentation: ApplicationPresentation

    def __post_init__(self) -> None:
        if not isinstance(self.surface, WindowClientSurface):
            raise TypeError("surface must be WindowClientSurface")
        if not isinstance(self.presentation, ApplicationPresentation):
            raise TypeError("presentation must be ApplicationPresentation")
        if not self.surface.bounds.contains_rect(self.presentation.bounds):
            raise ValueError(
                "application presentation bounds must be contained by "
                "window client bounds"
            )

    @property
    def window_id(self) -> WindowId:
        return self.surface.window_id

    @property
    def bounds(self) -> Rect:
        return self.presentation.bounds

    @property
    def bounds_client(self) -> Rect:
        return self.presentation.bounds


@dataclass(frozen=True, slots=True)
class LocatedApplicationPresentationInWindow:
    presentation: ApplicationPresentationInWindow
    provenance: ApplicationPresentationLocationProvenance
    confidence: float = 1.0

    def __post_init__(self) -> None:
        if not isinstance(self.presentation, ApplicationPresentationInWindow):
            raise TypeError("presentation must be ApplicationPresentationInWindow")
        located = LocatedApplicationPresentation(
            presentation=self.presentation.presentation,
            provenance=self.provenance,
            confidence=self.confidence,
        )
        object.__setattr__(self, "confidence", located.confidence)


@dataclass(frozen=True, slots=True)
class ApplicationPresentationInWindowUnavailable:
    window_id: WindowId
    reason: ApplicationPresentationInWindowFailureReason
    detail: str | None = None
    location_reason: ApplicationPresentationLocationFailureReason | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.window_id, WindowId):
            raise TypeError("window_id must be WindowId")
        if not isinstance(self.reason, ApplicationPresentationInWindowFailureReason):
            raise TypeError(
                "reason must be ApplicationPresentationInWindowFailureReason"
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
            is ApplicationPresentationInWindowFailureReason.PRESENTATION_NOT_LOCATED
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


ApplicationPresentationInWindowResult: TypeAlias = (
    LocatedApplicationPresentationInWindow | ApplicationPresentationInWindowUnavailable
)


def locate_application_presentation_in_window(
    window: WindowState,
    *,
    anchor: ApplicationPresentationCorrespondenceAnchor,
    locator: ApplicationPresentationLocator[WindowClientSurface],
) -> ApplicationPresentationInWindowResult:
    """Locate and anchor one presentation in a Window client-local surface."""

    if not isinstance(window, WindowState):
        raise TypeError("window must be WindowState")
    if not isinstance(anchor, ApplicationPresentationCorrespondenceAnchor):
        raise TypeError("anchor must be ApplicationPresentationCorrespondenceAnchor")
    if not hasattr(locator, "locate"):
        raise TypeError("locator must provide locate()")
    if window.client_surface is None:
        return ApplicationPresentationInWindowUnavailable(
            window_id=window.window_id,
            reason=(
                ApplicationPresentationInWindowFailureReason.CLIENT_SURFACE_UNAVAILABLE
            ),
        )

    surface = window.client_surface
    located = locator.locate(surface)
    if isinstance(located, ApplicationPresentationLocationUnavailable):
        return ApplicationPresentationInWindowUnavailable(
            window_id=window.window_id,
            reason=ApplicationPresentationInWindowFailureReason.PRESENTATION_NOT_LOCATED,
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
        raise ValueError(
            "locator result must belong to the supplied Window client surface"
        )

    client_bounds = surface.bounds
    if not client_bounds.contains_rect(located.bounds):
        return ApplicationPresentationInWindowUnavailable(
            window_id=window.window_id,
            reason=ApplicationPresentationInWindowFailureReason.BOUNDS_OUTSIDE_CLIENT,
            detail=(
                f"application presentation bounds {located.bounds} are outside "
                f"window client bounds {client_bounds}"
            ),
        )

    return LocatedApplicationPresentationInWindow(
        presentation=ApplicationPresentationInWindow(
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
    "ApplicationPresentationInWindow",
    "ApplicationPresentationInWindowFailureReason",
    "ApplicationPresentationInWindowResult",
    "ApplicationPresentationInWindowUnavailable",
    "LocatedApplicationPresentationInWindow",
    "locate_application_presentation_in_window",
]
