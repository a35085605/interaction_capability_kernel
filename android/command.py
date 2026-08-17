from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from android.identity import AndroidComponentName, AndroidPackageName, AndroidUserId
from native_attempt import NativeAttemptResult


@dataclass(frozen=True, slots=True)
class AndroidActivityLaunch:
    user_id: AndroidUserId
    component: AndroidComponentName

    def __post_init__(self) -> None:
        if not isinstance(self.user_id, AndroidUserId):
            raise TypeError("activity launch user_id must be AndroidUserId")
        if not isinstance(self.component, AndroidComponentName):
            raise TypeError("activity launch component must be AndroidComponentName")


@dataclass(frozen=True, slots=True)
class AndroidPackageForceStop:
    user_id: AndroidUserId
    package_name: AndroidPackageName

    def __post_init__(self) -> None:
        if not isinstance(self.user_id, AndroidUserId):
            raise TypeError("force-stop user_id must be AndroidUserId")
        if not isinstance(self.package_name, AndroidPackageName):
            raise TypeError("force-stop package_name must be AndroidPackageName")


class AndroidActivityLauncher(Protocol):
    def launch(self, operation: AndroidActivityLaunch) -> NativeAttemptResult:
        ...


class AndroidPackageForceStopper(Protocol):
    def force_stop(self, operation: AndroidPackageForceStop) -> NativeAttemptResult:
        ...


__all__ = [
    "AndroidActivityLaunch",
    "AndroidActivityLauncher",
    "AndroidPackageForceStop",
    "AndroidPackageForceStopper",
]
