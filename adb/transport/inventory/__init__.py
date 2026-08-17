"""ADB server-observed transport inventory facts and read-side contracts."""

from adb.transport.inventory.domain import (
    AdbConnectionState,
    AdbConnectionType,
    AdbDevicesSnapshot,
    AdbTrackedDevice,
)
from adb.transport.inventory.query import AdbDevicesSnapshotReader, AdbTrackedDeviceLookup

__all__ = [
    "AdbConnectionState",
    "AdbConnectionType",
    "AdbDevicesSnapshot",
    "AdbDevicesSnapshotReader",
    "AdbTrackedDevice",
    "AdbTrackedDeviceLookup",
]
