from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from numbers import Integral

from android.display import AndroidDisplayId
from android.identity import AndroidComponentName, AndroidPackageName, AndroidUserId


def _normalize_task_id(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError("Android task id must be an integer")
    normalized = int(value)
    if normalized < 0:
        raise ValueError("Android task id cannot be negative")
    return normalized


class AndroidPackageEnabledState(int, Enum):
    """Per-user PackageManager component-enabled setting."""

    DEFAULT = 0
    ENABLED = 1
    DISABLED = 2
    DISABLED_USER = 3
    DISABLED_UNTIL_USED = 4


@dataclass(frozen=True, slots=True)
class AndroidPackageState:
    """Per-user package availability facts from PackageManager state."""

    user_id: AndroidUserId
    package_name: AndroidPackageName
    installed: bool
    enabled_state: AndroidPackageEnabledState = AndroidPackageEnabledState.DEFAULT
    hidden: bool = False
    suspended: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.user_id, AndroidUserId):
            raise TypeError("package state user_id must be AndroidUserId")
        if not isinstance(self.package_name, AndroidPackageName):
            raise TypeError("package state package_name must be AndroidPackageName")
        if not isinstance(self.installed, bool):
            raise TypeError("package state installed must be bool")
        if not isinstance(self.enabled_state, AndroidPackageEnabledState):
            raise TypeError("package state enabled_state must be AndroidPackageEnabledState")
        if not isinstance(self.hidden, bool):
            raise TypeError("package state hidden must be bool")
        if not isinstance(self.suspended, bool):
            raise TypeError("package state suspended must be bool")

    @property
    def explicitly_disabled(self) -> bool:
        return self.enabled_state in {
            AndroidPackageEnabledState.DISABLED,
            AndroidPackageEnabledState.DISABLED_USER,
            AndroidPackageEnabledState.DISABLED_UNTIL_USED,
        }


@dataclass(frozen=True, slots=True)
class AndroidResumedActivity:
    """One resumed Android activity scoped to user, logical display, and task."""

    user_id: AndroidUserId
    display_id: AndroidDisplayId
    component: AndroidComponentName
    task_id: int

    def __post_init__(self) -> None:
        if not isinstance(self.user_id, AndroidUserId):
            raise TypeError("resumed activity user_id must be AndroidUserId")
        if not isinstance(self.display_id, AndroidDisplayId):
            raise TypeError("resumed activity display_id must be AndroidDisplayId")
        if not isinstance(self.component, AndroidComponentName):
            raise TypeError("resumed activity component must be AndroidComponentName")
        object.__setattr__(self, "task_id", _normalize_task_id(self.task_id))


@dataclass(frozen=True, slots=True)
class AndroidResumedActivitiesSnapshot:
    """Complete resumed-activity facts observed from the activity manager dump."""

    activities: tuple[AndroidResumedActivity, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.activities, tuple):
            raise TypeError("resumed activities must be a tuple")
        for index, activity in enumerate(self.activities):
            if not isinstance(activity, AndroidResumedActivity):
                raise TypeError(
                    f"resumed activities[{index}] must be AndroidResumedActivity"
                )


__all__ = [
    "AndroidPackageEnabledState",
    "AndroidPackageState",
    "AndroidResumedActivitiesSnapshot",
    "AndroidResumedActivity",
]
