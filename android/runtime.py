from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from android.identity import AndroidUserId


class AndroidBootState(str, Enum):
    """Minimal Android framework boot readiness observed through a native adapter."""

    BOOTING = "booting"
    BOOTED = "booted"


class AndroidUserPhase(str, Enum):
    BOOTING = "booting"
    RUNNING_LOCKED = "running_locked"
    RUNNING_UNLOCKING = "running_unlocking"
    RUNNING_UNLOCKED = "running_unlocked"
    STOPPING = "stopping"
    SHUTDOWN = "shutdown"


@dataclass(frozen=True, slots=True)
class AndroidUserState:
    user_id: AndroidUserId
    phase: AndroidUserPhase

    def __post_init__(self) -> None:
        if not isinstance(self.user_id, AndroidUserId):
            raise TypeError("Android user state user_id must be AndroidUserId")
        if not isinstance(self.phase, AndroidUserPhase):
            raise TypeError("Android user state phase must be AndroidUserPhase")


def _normalize_required_text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} cannot be empty")
    return normalized


@dataclass(frozen=True, slots=True)
class AndroidUserInfo:
    """One user/profile row from the Android user manager."""

    user_id: AndroidUserId
    name: str
    user_type: str
    flags: frozenset[str] = field(default_factory=frozenset)
    profile_group_id: AndroidUserId | None = None
    running: bool = False
    current: bool = False
    visible: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.user_id, AndroidUserId):
            raise TypeError("Android user info user_id must be AndroidUserId")
        object.__setattr__(
            self, "name", _normalize_required_text(self.name, field_name="Android user name")
        )
        object.__setattr__(
            self,
            "user_type",
            _normalize_required_text(self.user_type, field_name="Android user type"),
        )
        if not isinstance(self.flags, frozenset):
            raise TypeError("Android user flags must be a frozenset")
        for flag in self.flags:
            _normalize_required_text(flag, field_name="Android user flag")
        if self.profile_group_id is not None and not isinstance(
            self.profile_group_id, AndroidUserId
        ):
            raise TypeError("profile_group_id must be AndroidUserId or None")
        for field_name in ("running", "current", "visible"):
            if not isinstance(getattr(self, field_name), bool):
                raise TypeError(f"Android user {field_name} must be bool")


@dataclass(frozen=True, slots=True)
class AndroidUsersSnapshot:
    """Complete verbose user/profile listing for one supported user-manager response."""

    users: tuple[AndroidUserInfo, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.users, tuple):
            raise TypeError("Android users must be a tuple")
        seen: set[AndroidUserId] = set()
        for index, user in enumerate(self.users):
            if not isinstance(user, AndroidUserInfo):
                raise TypeError(f"Android users[{index}] must be AndroidUserInfo")
            if user.user_id in seen:
                raise ValueError("Android user ids must be unique within a snapshot")
            seen.add(user.user_id)


class AndroidPowerWakefulness(str, Enum):
    AWAKE = "awake"
    ASLEEP = "asleep"
    DOZING = "dozing"
    DREAMING = "dreaming"


@dataclass(frozen=True, slots=True)
class AndroidPowerState:
    wakefulness: AndroidPowerWakefulness

    def __post_init__(self) -> None:
        if not isinstance(self.wakefulness, AndroidPowerWakefulness):
            raise TypeError("Android power wakefulness must be AndroidPowerWakefulness")


@dataclass(frozen=True, slots=True)
class AndroidKeyguardState:
    showing: bool

    def __post_init__(self) -> None:
        if not isinstance(self.showing, bool):
            raise TypeError("Android keyguard showing must be bool")


__all__ = [
    "AndroidBootState",
    "AndroidKeyguardState",
    "AndroidPowerState",
    "AndroidPowerWakefulness",
    "AndroidUserInfo",
    "AndroidUserPhase",
    "AndroidUsersSnapshot",
    "AndroidUserState",
]
