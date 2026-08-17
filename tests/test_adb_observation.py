from __future__ import annotations

from collections.abc import Iterator
import importlib.util
import unittest

from adb.transport.inventory import AdbConnectionState, AdbDevicesSnapshot, AdbTrackedDevice
from adb.transport.observation import AdbDevicesSnapshotSource


class _Source:
    def __init__(self, snapshots: tuple[AdbDevicesSnapshot, ...]) -> None:
        self._snapshots = snapshots
        self.closed = False

    def snapshots(self) -> Iterator[AdbDevicesSnapshot]:
        yield from self._snapshots

    def close(self) -> None:
        self.closed = True


class AdbObservationContractTests(unittest.TestCase):
    def test_snapshot_source_exposes_complete_snapshots(self) -> None:
        first = AdbDevicesSnapshot(
            (AdbTrackedDevice(serial="device-1", state=AdbConnectionState.OFFLINE),)
        )
        second = AdbDevicesSnapshot(
            (AdbTrackedDevice(serial="device-1", state=AdbConnectionState.DEVICE),)
        )
        source: AdbDevicesSnapshotSource = _Source((first, second))

        self.assertEqual(tuple(source.snapshots()), (first, second))
        source.close()
        self.assertTrue(source.closed)  # type: ignore[attr-defined]

    def test_low_level_observation_does_not_synthesize_state_change_events(self) -> None:
        self.assertIsNone(importlib.util.find_spec("adb.events"))

    def test_tracked_device_is_not_a_peer_adb_namespace(self) -> None:
        self.assertIsNone(importlib.util.find_spec("adb.tracked_device"))
        self.assertIsNotNone(importlib.util.find_spec("adb.transport.inventory"))
        self.assertIsNotNone(importlib.util.find_spec("adb.transport.observation"))


if __name__ == "__main__":
    unittest.main()
