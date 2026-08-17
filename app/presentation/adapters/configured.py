from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

from app.presentation.location import (
    ApplicationPresentationLocationProvenance,
    ApplicationPresentationLocationResult,
    LocatedApplicationPresentationInSurface,
)
from geometry import Rect


SurfaceT = TypeVar("SurfaceT")


@dataclass(frozen=True, slots=True)
class ConfiguredApplicationPresentationLocator(Generic[SurfaceT]):
    """Locate a presentation at caller-configured bounds in any surface."""

    bounds: Rect
    locator_id: str = "application_presentation.configured"

    def __post_init__(self) -> None:
        if not isinstance(self.bounds, Rect):
            raise TypeError("bounds must be Rect")
        provenance = ApplicationPresentationLocationProvenance(self.locator_id)
        object.__setattr__(self, "locator_id", provenance.locator_id)

    def locate(
        self,
        surface: SurfaceT,
    ) -> ApplicationPresentationLocationResult[SurfaceT]:
        return LocatedApplicationPresentationInSurface(
            surface=surface,
            bounds=self.bounds,
            provenance=ApplicationPresentationLocationProvenance(self.locator_id),
        )


__all__ = ["ConfiguredApplicationPresentationLocator"]
