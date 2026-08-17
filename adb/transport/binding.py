from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from adb.configuration import AdbServerId, AdbTransportBindingId
from adb.transport.inventory.domain import AdbDevicesSnapshot, AdbTrackedDevice
from adb.transport.selection import (
    AdbTransportById,
    AdbTransportBySerial,
    AdbTransportSelector,
)


def _normalize_optional_text(value: object, *, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string or None")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} cannot be empty")
    return normalized


def _require_selector(value: object) -> AdbTransportSelector:
    if not isinstance(value, (AdbTransportBySerial, AdbTransportById)):
        raise TypeError("inventory_selector must be an ADB transport selector")
    return value


@dataclass(frozen=True, slots=True)
class AdbTransportBindingConfiguration:
    """Caller-owned configuration for resolving and optionally establishing one transport.

    ``inventory_selector`` is explicit and independent from ``connect_address`` so callers do
    not have to assume that the address passed to ``adb connect`` is identical to the serial
    reported later by the ADB transport inventory.
    """

    server_id: AdbServerId
    binding_id: AdbTransportBindingId
    inventory_selector: AdbTransportSelector
    connect_address: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.server_id, AdbServerId):
            raise TypeError("server_id must be AdbServerId")
        if not isinstance(self.binding_id, AdbTransportBindingId):
            raise TypeError("binding_id must be AdbTransportBindingId")
        _require_selector(self.inventory_selector)
        object.__setattr__(
            self,
            "connect_address",
            _normalize_optional_text(
                self.connect_address,
                field_name="ADB transport connect address",
            ),
        )


class AdbTransportBindingResolutionStatus(str, Enum):
    """How one configured binding resolves against one complete inventory snapshot."""

    ABSENT = "absent"
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True, slots=True)
class AdbTransportBindingResolution:
    """Pure projection of one configured transport binding into one inventory snapshot."""

    configuration: AdbTransportBindingConfiguration
    status: AdbTransportBindingResolutionStatus
    matches: tuple[AdbTrackedDevice, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.configuration, AdbTransportBindingConfiguration):
            raise TypeError("configuration must be AdbTransportBindingConfiguration")
        if not isinstance(self.status, AdbTransportBindingResolutionStatus):
            raise TypeError("status must be AdbTransportBindingResolutionStatus")
        if not isinstance(self.matches, tuple) or not all(
            isinstance(row, AdbTrackedDevice) for row in self.matches
        ):
            raise TypeError("matches must be a tuple of AdbTrackedDevice values")
        expected = (
            AdbTransportBindingResolutionStatus.ABSENT
            if not self.matches
            else AdbTransportBindingResolutionStatus.RESOLVED
            if len(self.matches) == 1
            else AdbTransportBindingResolutionStatus.AMBIGUOUS
        )
        if self.status is not expected:
            raise ValueError("resolution status does not match the number of matching rows")

    @property
    def row(self) -> AdbTrackedDevice | None:
        return self.matches[0] if self.status is AdbTransportBindingResolutionStatus.RESOLVED else None


def resolve_transport_binding(
    configuration: AdbTransportBindingConfiguration,
    snapshot: AdbDevicesSnapshot,
) -> AdbTransportBindingResolution:
    """Resolve one configured binding without interpreting transport state readiness."""

    if not isinstance(configuration, AdbTransportBindingConfiguration):
        raise TypeError("configuration must be AdbTransportBindingConfiguration")
    if not isinstance(snapshot, AdbDevicesSnapshot):
        raise TypeError("snapshot must be AdbDevicesSnapshot")

    selector = configuration.inventory_selector
    if isinstance(selector, AdbTransportBySerial):
        matches = tuple(
            row for row in snapshot.devices if row.serial == selector.serial.value
        )
    elif isinstance(selector, AdbTransportById):
        matches = tuple(
            row for row in snapshot.devices if row.transport_id == selector.transport_id
        )
    else:  # pragma: no cover - guarded by configuration validation
        raise TypeError("inventory_selector must be an ADB transport selector")

    status = (
        AdbTransportBindingResolutionStatus.ABSENT
        if not matches
        else AdbTransportBindingResolutionStatus.RESOLVED
        if len(matches) == 1
        else AdbTransportBindingResolutionStatus.AMBIGUOUS
    )
    return AdbTransportBindingResolution(configuration, status, matches)


__all__ = [
    "AdbTransportBindingConfiguration",
    "AdbTransportBindingResolution",
    "AdbTransportBindingResolutionStatus",
    "resolve_transport_binding",
]
