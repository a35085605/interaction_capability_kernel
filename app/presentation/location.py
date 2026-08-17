from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from numbers import Real
from typing import Generic, Protocol, TypeAlias, TypeVar

from app.presentation.model import ApplicationPresentation
from geometry import Rect


SurfaceT = TypeVar("SurfaceT")


def _normalize_non_empty_text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(
            f"{field_name} must be a string, got {type(value).__name__}"
        )
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} cannot be empty")
    return normalized


def _normalize_optional_text(
    value: object,
    *,
    field_name: str,
) -> str | None:
    if value is None:
        return None
    return _normalize_non_empty_text(value, field_name=field_name)


def _normalize_confidence(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError("application presentation confidence must be a real number")
    normalized = float(value)
    if not 0.0 <= normalized <= 1.0:
        raise ValueError(
            "application presentation confidence must be between 0 and 1"
        )
    return normalized


class ApplicationPresentationLocationFailureReason(str, Enum):
    NOT_FOUND = "not_found"
    AMBIGUOUS = "ambiguous"
    UNSUPPORTED_LAYOUT = "unsupported_layout"


@dataclass(frozen=True, slots=True)
class ApplicationPresentationLocationProvenance:
    locator_id: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "locator_id",
            _normalize_non_empty_text(
                self.locator_id,
                field_name="application presentation locator id",
            ),
        )


@dataclass(frozen=True, slots=True)
class LocatedApplicationPresentationInSurface(Generic[SurfaceT]):
    """Application-presentation geometry located in one caller-owned surface.

    The surface owns the identity and meaning of ``bounds``. The locator records
    where the presentation was found and how, but it does not issue or infer a
    presentation-correspondence anchor.
    """

    surface: SurfaceT
    bounds: Rect
    provenance: ApplicationPresentationLocationProvenance
    confidence: float = 1.0

    def __post_init__(self) -> None:
        if self.surface is None:
            raise TypeError("surface cannot be None")
        if not isinstance(self.bounds, Rect):
            raise TypeError("application presentation bounds must be Rect")
        if not isinstance(
            self.provenance,
            ApplicationPresentationLocationProvenance,
        ):
            raise TypeError(
                "provenance must be ApplicationPresentationLocationProvenance"
            )
        object.__setattr__(
            self,
            "confidence",
            _normalize_confidence(self.confidence),
        )


@dataclass(frozen=True, slots=True)
class ApplicationPresentationLocationUnavailable:
    reason: ApplicationPresentationLocationFailureReason
    detail: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.reason, ApplicationPresentationLocationFailureReason):
            raise TypeError(
                "reason must be ApplicationPresentationLocationFailureReason"
            )
        object.__setattr__(
            self,
            "detail",
            _normalize_optional_text(
                self.detail,
                field_name="application presentation location failure detail",
            ),
        )


ApplicationPresentationLocationResult: TypeAlias = (
    LocatedApplicationPresentationInSurface[SurfaceT]
    | ApplicationPresentationLocationUnavailable
)


class ApplicationPresentationLocator(Protocol[SurfaceT]):
    """Locate the application presentation in one caller-owned surface.

    The caller selects and configures the locator. Locator-specific knowledge such
    as configured bounds, monitor identity, native metadata, or visual recognition
    stays behind this port rather than being modeled as a generic search region.
    """

    def locate(
        self,
        surface: SurfaceT,
    ) -> ApplicationPresentationLocationResult[SurfaceT]:
        ...


@dataclass(frozen=True, slots=True)
class LocatedApplicationPresentation:
    presentation: ApplicationPresentation
    provenance: ApplicationPresentationLocationProvenance
    confidence: float = 1.0

    def __post_init__(self) -> None:
        if not isinstance(self.presentation, ApplicationPresentation):
            raise TypeError("presentation must be ApplicationPresentation")
        if not isinstance(
            self.provenance,
            ApplicationPresentationLocationProvenance,
        ):
            raise TypeError(
                "provenance must be ApplicationPresentationLocationProvenance"
            )
        object.__setattr__(
            self,
            "confidence",
            _normalize_confidence(self.confidence),
        )


__all__ = [
    "ApplicationPresentationLocationFailureReason",
    "ApplicationPresentationLocationProvenance",
    "ApplicationPresentationLocationResult",
    "ApplicationPresentationLocationUnavailable",
    "ApplicationPresentationLocator",
    "LocatedApplicationPresentation",
    "LocatedApplicationPresentationInSurface",
]
