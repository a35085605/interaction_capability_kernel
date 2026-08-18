from __future__ import annotations

from dataclasses import dataclass

from adb.server.endpoint import AdbServerEndpoint


def _normalize_required_text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string, got {type(value).__name__}")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} cannot be empty")
    return normalized


@dataclass(frozen=True, slots=True, order=True)
class AdbServerId:
    """Caller-owned identity for one configured ADB server."""

    value: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "value",
            _normalize_required_text(self.value, field_name="ADB server id"),
        )

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class AdbServerConfiguration:
    """Caller-owned binding from one ADB server identity to its smart-socket endpoint."""

    server_id: AdbServerId
    endpoint: AdbServerEndpoint

    def __post_init__(self) -> None:
        if not isinstance(self.server_id, AdbServerId):
            raise TypeError("server_id must be AdbServerId")
        if not isinstance(self.endpoint, AdbServerEndpoint):
            raise TypeError("endpoint must be AdbServerEndpoint")


__all__ = [
    "AdbServerConfiguration",
    "AdbServerId",
]
