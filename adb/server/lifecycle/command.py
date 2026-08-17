from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from adb.configuration import AdbServerId
from native_attempt import NativeAttemptResult


@dataclass(frozen=True, slots=True)
class AdbServerStart:
    """Request one native attempt to start one configured ADB server."""

    server_id: AdbServerId

    def __post_init__(self) -> None:
        if not isinstance(self.server_id, AdbServerId):
            raise TypeError("server_id must be AdbServerId")


@dataclass(frozen=True, slots=True)
class AdbServerStop:
    """Request one native attempt to stop one configured ADB server."""

    server_id: AdbServerId

    def __post_init__(self) -> None:
        if not isinstance(self.server_id, AdbServerId):
            raise TypeError("server_id must be AdbServerId")


class AdbServerStarter(Protocol):
    def start(self, operation: AdbServerStart) -> NativeAttemptResult: ...


class AdbServerStopper(Protocol):
    def stop(self, operation: AdbServerStop) -> NativeAttemptResult: ...


__all__ = ["AdbServerStart", "AdbServerStarter", "AdbServerStop", "AdbServerStopper"]
