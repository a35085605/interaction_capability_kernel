from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from android.display import AndroidDisplayId
from android.identity import AndroidComponentName, AndroidPackageName, AndroidUserId
from geometry import Rect


def _normalize_required_text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} cannot be empty")
    return normalized


def _normalize_optional_text(value: object, *, field_name: str) -> str | None:
    if value is None:
        return None
    return _normalize_required_text(value, field_name=field_name)


@dataclass(frozen=True, slots=True, order=True)
class AndroidWindowId:
    """Time-scoped WindowManager window identity from a native window dump."""

    value: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "value",
            _normalize_required_text(self.value, field_name="Android window id"),
        )

    def __str__(self) -> str:
        return self.value


class AndroidWindowViewVisibility(int, Enum):
    """Android View visibility value reported for one WindowState."""

    VISIBLE = 0
    INVISIBLE = 4
    GONE = 8


@dataclass(frozen=True, slots=True)
class AndroidWindowState:
    """Observed WindowManager facts for one native Android window.

    ``view_visibility`` and ``has_surface`` stay separate instead of being collapsed into a
    caller-level "usable/visible application" judgment. ``focused`` records only native WM focus.
    ``windowing_mode`` preserves the native textual mode when present and remains an open value.
    """

    window_id: AndroidWindowId
    display_id: AndroidDisplayId
    bounds: Rect
    view_visibility: AndroidWindowViewVisibility
    has_surface: bool
    focused: bool
    user_id: AndroidUserId | None = None
    package_name: AndroidPackageName | None = None
    component: AndroidComponentName | None = None
    windowing_mode: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.window_id, AndroidWindowId):
            raise TypeError("window_id must be AndroidWindowId")
        if not isinstance(self.display_id, AndroidDisplayId):
            raise TypeError("display_id must be AndroidDisplayId")
        if not isinstance(self.bounds, Rect):
            raise TypeError("Android window bounds must be Rect")
        if not isinstance(self.view_visibility, AndroidWindowViewVisibility):
            raise TypeError("view_visibility must be AndroidWindowViewVisibility")
        if not isinstance(self.has_surface, bool):
            raise TypeError("has_surface must be bool")
        if not isinstance(self.focused, bool):
            raise TypeError("focused must be bool")
        if self.user_id is not None and not isinstance(self.user_id, AndroidUserId):
            raise TypeError("user_id must be AndroidUserId or None")
        if self.package_name is not None and not isinstance(
            self.package_name, AndroidPackageName
        ):
            raise TypeError("package_name must be AndroidPackageName or None")
        if self.component is not None and not isinstance(
            self.component, AndroidComponentName
        ):
            raise TypeError("component must be AndroidComponentName or None")
        if self.component is not None and self.package_name is not None:
            if self.component.package != self.package_name:
                raise ValueError("window component package must match package_name")
        object.__setattr__(
            self,
            "windowing_mode",
            _normalize_optional_text(
                self.windowing_mode, field_name="Android windowing mode"
            ),
        )

    @property
    def view_visible(self) -> bool:
        return self.view_visibility is AndroidWindowViewVisibility.VISIBLE


@dataclass(frozen=True, slots=True)
class AndroidWindowsSnapshot:
    """Complete listing for the supported WindowManager window-dump format."""

    windows: tuple[AndroidWindowState, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.windows, tuple):
            raise TypeError("Android windows must be a tuple")
        seen: set[AndroidWindowId] = set()
        for index, window in enumerate(self.windows):
            if not isinstance(window, AndroidWindowState):
                raise TypeError(f"Android windows[{index}] must be AndroidWindowState")
            if window.window_id in seen:
                raise ValueError("Android window ids must be unique within a snapshot")
            seen.add(window.window_id)


class AndroidDisplayOcclusionKind(str, Enum):
    STATUS_BAR = "status_bar"
    NAVIGATION_BAR = "navigation_bar"
    DISPLAY_CUTOUT = "display_cutout"
    IME = "ime"


@dataclass(frozen=True, slots=True)
class AndroidDisplayOcclusion:
    """One WindowInsets source that may occlude application content."""

    kind: AndroidDisplayOcclusionKind
    bounds: Rect
    visible: bool

    def __post_init__(self) -> None:
        if not isinstance(self.kind, AndroidDisplayOcclusionKind):
            raise TypeError("occlusion kind must be AndroidDisplayOcclusionKind")
        if not isinstance(self.bounds, Rect):
            raise TypeError("occlusion bounds must be Rect")
        if not isinstance(self.visible, bool):
            raise TypeError("occlusion visible must be bool")


@dataclass(frozen=True, slots=True)
class AndroidDisplayOcclusionsSnapshot:
    """Status/navigation/cutout/IME inset sources for one logical display."""

    display_id: AndroidDisplayId
    occlusions: tuple[AndroidDisplayOcclusion, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.display_id, AndroidDisplayId):
            raise TypeError("display_id must be AndroidDisplayId")
        if not isinstance(self.occlusions, tuple):
            raise TypeError("Android display occlusions must be a tuple")
        for index, occlusion in enumerate(self.occlusions):
            if not isinstance(occlusion, AndroidDisplayOcclusion):
                raise TypeError(
                    f"Android display occlusions[{index}] must be AndroidDisplayOcclusion"
                )


__all__ = [
    "AndroidDisplayOcclusion",
    "AndroidDisplayOcclusionKind",
    "AndroidDisplayOcclusionsSnapshot",
    "AndroidWindowId",
    "AndroidWindowState",
    "AndroidWindowsSnapshot",
    "AndroidWindowViewVisibility",
]
