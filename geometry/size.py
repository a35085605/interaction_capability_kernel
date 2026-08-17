from __future__ import annotations

from dataclasses import dataclass
from numbers import Integral


def _normalize_positive_integer(value: object, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError(
            f"{field_name} must be an integer, "
            f"got {type(value).__name__}"
        )
    normalized = int(value)
    if normalized <= 0:
        raise ValueError(f"{field_name} must be greater than zero")
    return normalized


@dataclass(frozen=True, slots=True)
class Size:
    """Immutable positive raster or coordinate-space dimensions."""

    width: int
    height: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "width",
            _normalize_positive_integer(self.width, field_name="size width"),
        )
        object.__setattr__(
            self,
            "height",
            _normalize_positive_integer(self.height, field_name="size height"),
        )

    @property
    def area(self) -> int:
        return self.width * self.height
