from __future__ import annotations

from dataclasses import dataclass

from app.presentation.anchor import ApplicationPresentationCorrespondenceAnchor
from geometry import Rect


@dataclass(frozen=True, slots=True)
class ApplicationPresentation:
    """Full application-presentation rectangle with caller-declared correspondence."""

    anchor: ApplicationPresentationCorrespondenceAnchor
    bounds: Rect

    def __post_init__(self) -> None:
        if not isinstance(
            self.anchor,
            ApplicationPresentationCorrespondenceAnchor,
        ):
            raise TypeError(
                "application presentation anchor must be "
                "ApplicationPresentationCorrespondenceAnchor"
            )
        if not isinstance(self.bounds, Rect):
            raise TypeError("application presentation bounds must be Rect")
