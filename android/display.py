from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from numbers import Integral
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from android.spatial import AndroidDisplaySurface

from geometry import Rect, Size


def _normalize_display_id(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError("Android display id must be an integer")
    normalized = int(value)
    if normalized < 0:
        raise ValueError("Android display id cannot be negative")
    return normalized


def _normalize_physical_display_id(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError("Android physical display id must be an integer")
    normalized = int(value)
    if normalized < 0:
        raise ValueError("Android physical display id cannot be negative")
    return normalized


def _normalize_optional_non_negative_integer(value: object, *, field_name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError(f"{field_name} must be an integer or None")
    normalized = int(value)
    if normalized < 0:
        raise ValueError(f"{field_name} cannot be negative")
    return normalized


def _normalize_optional_text(value: object, *, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string or None")
    normalized = value.strip()
    return normalized or None


def _normalize_density_dpi(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError("Android display density_dpi must be an integer or None")
    normalized = int(value)
    if normalized <= 0:
        raise ValueError("Android display density_dpi must be greater than zero")
    return normalized


class AndroidDisplayRotation(int, Enum):
    """Clockwise display rotation in degrees.

    Android framework ``Surface.ROTATION_*`` values use quarter-turn codes 0..3.
    Adapters must normalize those native values through ``from_surface_rotation()``
    before constructing ``AndroidDisplayState``.
    """

    ROTATION_0 = 0
    ROTATION_90 = 90
    ROTATION_180 = 180
    ROTATION_270 = 270

    @classmethod
    def from_surface_rotation(cls, value: object) -> AndroidDisplayRotation:
        """Convert Android ``Surface.ROTATION_*`` code 0..3 to degrees."""

        if isinstance(value, bool) or not isinstance(value, Integral):
            raise TypeError("Android surface rotation must be an integer")
        normalized = int(value)
        rotations = (
            cls.ROTATION_0,
            cls.ROTATION_90,
            cls.ROTATION_180,
            cls.ROTATION_270,
        )
        if not 0 <= normalized < len(rotations):
            raise ValueError("Android surface rotation must be between 0 and 3")
        return rotations[normalized]


@dataclass(frozen=True, slots=True, order=True)
class AndroidDisplayId:
    """Android runtime logical display identifier."""

    value: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _normalize_display_id(self.value))

    def __int__(self) -> int:
        return self.value

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True, order=True)
class AndroidPhysicalDisplayId:
    """SurfaceFlinger physical display identity used by deterministic screencap."""

    value: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _normalize_physical_display_id(self.value))

    def __int__(self) -> int:
        return self.value

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class AndroidPhysicalDisplayState:
    """Physical display facts reported by ``dumpsys SurfaceFlinger --display-id``."""

    display_id: AndroidPhysicalDisplayId
    hwc_display_id: int | None = None
    port: int | None = None
    pnp_id: str | None = None
    display_name: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.display_id, AndroidPhysicalDisplayId):
            raise TypeError("physical display_id must be AndroidPhysicalDisplayId")
        object.__setattr__(
            self,
            "hwc_display_id",
            _normalize_optional_non_negative_integer(
                self.hwc_display_id, field_name="Android HWC display id"
            ),
        )
        object.__setattr__(
            self,
            "port",
            _normalize_optional_non_negative_integer(
                self.port, field_name="Android display port"
            ),
        )
        object.__setattr__(
            self,
            "pnp_id",
            _normalize_optional_text(self.pnp_id, field_name="Android display pnp_id"),
        )
        object.__setattr__(
            self,
            "display_name",
            _normalize_optional_text(
                self.display_name, field_name="Android physical display name"
            ),
        )


@dataclass(frozen=True, slots=True)
class AndroidPhysicalDisplaysSnapshot:
    displays: tuple[AndroidPhysicalDisplayState, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.displays, tuple):
            raise TypeError("Android physical displays must be a tuple")
        for index, display in enumerate(self.displays):
            if not isinstance(display, AndroidPhysicalDisplayState):
                raise TypeError(
                    f"Android physical displays[{index}] must be AndroidPhysicalDisplayState"
                )


@dataclass(frozen=True, slots=True)
class AndroidDisplayState:
    """Current observed facts for one Android logical display.

    ``bounds`` is the current logical display coordinate surface used by display-local
    interaction mechanisms. ``physical_size`` is optional physical/native panel metadata
    and must not be substituted for the current logical bounds.
    """

    display_id: AndroidDisplayId
    bounds: Rect
    rotation: AndroidDisplayRotation
    density_dpi: int | None = None
    physical_size: Size | None = None
    physical_display_id: AndroidPhysicalDisplayId | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.display_id, AndroidDisplayId):
            raise TypeError("Android display_id must be AndroidDisplayId")
        if not isinstance(self.bounds, Rect):
            raise TypeError("Android display bounds must be Rect")
        if not isinstance(self.rotation, AndroidDisplayRotation):
            raise TypeError("Android display rotation must be AndroidDisplayRotation")
        if self.physical_size is not None and not isinstance(self.physical_size, Size):
            raise TypeError("Android display physical_size must be Size or None")
        if self.physical_display_id is not None and not isinstance(
            self.physical_display_id, AndroidPhysicalDisplayId
        ):
            raise TypeError(
                "Android display physical_display_id must be AndroidPhysicalDisplayId or None"
            )

        object.__setattr__(
            self,
            "density_dpi",
            _normalize_density_dpi(self.density_dpi),
        )

    @property
    def surface(self) -> AndroidDisplaySurface:
        """Return the current Android display spatial surface for these facts."""

        from android.spatial import AndroidDisplaySurface

        return AndroidDisplaySurface(display_id=self.display_id, bounds=self.bounds)


@dataclass(frozen=True, slots=True)
class AndroidDisplaysSnapshot:
    """Complete observed logical-display listing for one Android runtime."""

    displays: tuple[AndroidDisplayState, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.displays, tuple):
            raise TypeError("Android displays must be a tuple")
        for index, display in enumerate(self.displays):
            if not isinstance(display, AndroidDisplayState):
                raise TypeError(
                    f"Android displays[{index}] must be AndroidDisplayState"
                )


__all__ = [
    "AndroidDisplayId",
    "AndroidDisplayRotation",
    "AndroidPhysicalDisplayId",
    "AndroidPhysicalDisplayState",
    "AndroidPhysicalDisplaysSnapshot",
    "AndroidDisplayState",
    "AndroidDisplaysSnapshot",
]
