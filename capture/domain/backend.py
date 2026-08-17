from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


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


@dataclass(frozen=True, slots=True)
class CaptureBackendProfile:
    """Stable identity of one capture backend implementation/configuration."""

    backend_id: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "backend_id",
            _normalize_non_empty_text(
                self.backend_id,
                field_name="capture backend id",
            ),
        )


class CaptureUnavailableReason(str, Enum):
    """Why one read-only acquisition attempt did not produce a frame."""

    SOURCE_UNAVAILABLE = "source_unavailable"
    PERMISSION_DENIED = "permission_denied"
    TRANSIENT_FAILURE = "transient_failure"


@dataclass(frozen=True, slots=True)
class CaptureUnavailable:
    """Typed non-exception result for an expected acquisition failure."""

    backend_id: str
    reason: CaptureUnavailableReason
    detail: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.reason, CaptureUnavailableReason):
            raise TypeError("reason must be CaptureUnavailableReason")
        object.__setattr__(
            self,
            "backend_id",
            _normalize_non_empty_text(
                self.backend_id,
                field_name="capture backend id",
            ),
        )
        object.__setattr__(
            self,
            "detail",
            _normalize_optional_text(
                self.detail,
                field_name="capture unavailable detail",
            ),
        )


__all__ = [
    "CaptureBackendProfile",
    "CaptureUnavailable",
    "CaptureUnavailableReason",
]
