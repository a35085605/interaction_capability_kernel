from __future__ import annotations

import unittest

import adb
from adb.transport.inventory import AdbDevicesSnapshot, AdbTrackedDevice
from adb.transport.inventory.adapters import find_tracked_device
from adb.transport import (
    AdbDeviceSerial,
    AdbTransportById,
    AdbTransportBySerial,
    AdbTransportId,
)


class AdbSelectionTests(unittest.TestCase):
    def test_serial_and_transport_id_are_typed_native_selection_values(self) -> None:
        serial = AdbDeviceSerial(" emulator-5554 ")
        transport_id = AdbTransportId(17)

        self.assertEqual(serial.value, "emulator-5554")
        self.assertEqual(int(transport_id), 17)
        self.assertEqual(AdbTransportBySerial(serial).serial, serial)
        self.assertEqual(AdbTransportById(transport_id).transport_id, transport_id)

        with self.assertRaises(ValueError):
            AdbTransportId(0)

    def test_tracked_device_normalizes_native_transport_identity(self) -> None:
        self.assertEqual(AdbTrackedDevice(transport_id=9).transport_id, AdbTransportId(9))
        self.assertEqual(AdbTrackedDevice(transport_id=0).transport_id, 0)

    def test_single_device_lookup_is_derived_from_complete_snapshot(self) -> None:
        first = AdbTrackedDevice(serial="a", transport_id=11)
        second = AdbTrackedDevice(serial="b", transport_id=12)
        snapshot = AdbDevicesSnapshot((first, second))

        self.assertIs(
            find_tracked_device(snapshot, AdbTransportBySerial(AdbDeviceSerial("b"))),
            second,
        )
        self.assertIs(
            find_tracked_device(snapshot, AdbTransportById(AdbTransportId(11))),
            first,
        )

    def test_internal_service_client_is_not_public_adb_capability(self) -> None:
        self.assertFalse(hasattr(adb, "AdbServiceClient"))
        self.assertFalse(hasattr(adb, "shell"))


if __name__ == "__main__":
    unittest.main()
