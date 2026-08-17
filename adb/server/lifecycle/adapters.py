from __future__ import annotations

from dataclasses import dataclass

from adb._internal.subprocess import normalize_executable, normalize_timeout, require_operation_server, run_adb, server_args
from adb.configuration import AdbServerConfiguration
from adb.server.lifecycle.command import AdbServerStart, AdbServerStop
from native_attempt import NativeAttemptResult


@dataclass(frozen=True, slots=True)
class SubprocessAdbServer:
    """Execute one configured ADB server lifecycle command per bounded CLI attempt."""

    configuration: AdbServerConfiguration
    executable: str = "adb"
    timeout_seconds: float = 10.0

    def __post_init__(self) -> None:
        if not isinstance(self.configuration, AdbServerConfiguration):
            raise TypeError("configuration must be AdbServerConfiguration")
        object.__setattr__(self, "executable", normalize_executable(self.executable))
        object.__setattr__(self, "timeout_seconds", normalize_timeout(self.timeout_seconds))

    def start(self, operation: AdbServerStart) -> NativeAttemptResult:
        if not isinstance(operation, AdbServerStart):
            raise TypeError("operation must be AdbServerStart")
        require_operation_server(self.configuration, operation.server_id)
        return run_adb(self.executable, self.timeout_seconds, [*server_args(self.configuration), "start-server"])

    def stop(self, operation: AdbServerStop) -> NativeAttemptResult:
        if not isinstance(operation, AdbServerStop):
            raise TypeError("operation must be AdbServerStop")
        require_operation_server(self.configuration, operation.server_id)
        return run_adb(self.executable, self.timeout_seconds, [*server_args(self.configuration), "kill-server"])


__all__ = ["SubprocessAdbServer"]
