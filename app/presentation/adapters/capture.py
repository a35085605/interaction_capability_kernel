from __future__ import annotations

from dataclasses import dataclass

from app.presentation.location import (
    ApplicationPresentationLocationProvenance,
    ApplicationPresentationLocationResult,
    LocatedApplicationPresentationInSurface,
)
from geometry import Rect
from capture import CapturedFrame


@dataclass(frozen=True, slots=True)
class FullCapturedFrameApplicationPresentationLocator:
    """Treat the complete captured frame as the application presentation."""

    locator_id: str = "application_presentation.full_captured_frame"

    def __post_init__(self) -> None:
        provenance = ApplicationPresentationLocationProvenance(self.locator_id)
        object.__setattr__(self, "locator_id", provenance.locator_id)

    def locate(
        self,
        surface: CapturedFrame,
    ) -> ApplicationPresentationLocationResult[CapturedFrame]:
        if not isinstance(surface, CapturedFrame):
            raise TypeError("surface must be CapturedFrame")
        return LocatedApplicationPresentationInSurface(
            surface=surface,
            bounds=Rect(
                x=0,
                y=0,
                width=surface.info.size.width,
                height=surface.info.size.height,
            ),
            provenance=ApplicationPresentationLocationProvenance(self.locator_id),
        )


__all__ = ["FullCapturedFrameApplicationPresentationLocator"]
