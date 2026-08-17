from __future__ import annotations

from dataclasses import dataclass


def _normalize_non_empty_text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(
            f"{field_name} must be a string, got {type(value).__name__}"
        )
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} cannot be empty")
    return normalized


@dataclass(frozen=True, slots=True, order=True)
class ApplicationPresentationCorrespondenceAnchor:
    """Caller assertion that equally anchored full presentations may be mapped
    by an invertible axis-aligned transform.
    """

    value: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "value",
            _normalize_non_empty_text(
                self.value,
                field_name="application presentation correspondence anchor",
            ),
        )

    def __str__(self) -> str:
        return self.value


__all__ = ["ApplicationPresentationCorrespondenceAnchor"]
