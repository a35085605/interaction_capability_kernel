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
class ApplicationId:
    """Stable caller-known logical identity of one software application.

    Capture backends and native inspectors do not infer or own this identity. It is
    application-domain vocabulary that higher-level composition may use without
    becoming part of either capability boundary.
    """

    value: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "value",
            _normalize_non_empty_text(
                self.value,
                field_name="application id",
            ),
        )

    def __str__(self) -> str:
        return self.value


__all__ = ["ApplicationId"]
