from __future__ import annotations

import unittest

from adb.configuration import AdbServerId
from adb.transport.inventory import (
    AdbConnectionState,
    AdbConnectionType,
    AdbDevicesSnapshot,
    AdbTrackedDevice,
)
from adb.server import AdbMdnsBackend, AdbServerEndpoint, AdbServerStatus, AdbUsbBackend
from adb.transport import AdbDeviceSerial, AdbTransportId


class AdbIdentityTests(unittest.TestCase):
    def test_server_id_is_caller_owned_while_serial_is_native_selection(self) -> None:
        self.assertEqual(str(AdbServerId(" local-adb ")), "local-adb")
        self.assertEqual(str(AdbDeviceSerial(" emulator-5554 ")), "emulator-5554")


class AdbTrackedDeviceTests(unittest.TestCase):
    def test_connection_state_matches_aosp_numeric_values(self) -> None:
        self.assertEqual(int(AdbConnectionState.ANY), 0)
        self.assertEqual(int(AdbConnectionState.NOPERMISSION), 4)
        self.assertEqual(int(AdbConnectionState.DEVICE), 8)
        self.assertEqual(int(AdbConnectionState.RESCUE), 12)

    def test_connection_type_matches_aosp_numeric_values(self) -> None:
        self.assertEqual(int(AdbConnectionType.UNKNOWN), 0)
        self.assertEqual(int(AdbConnectionType.USB), 1)
        self.assertEqual(int(AdbConnectionType.SOCKET), 2)

    def test_tracked_device_mirrors_host_proto_fields(self) -> None:
        device = AdbTrackedDevice(
            serial="emulator-5554",
            state=AdbConnectionState.DEVICE,
            bus_address="1-1",
            product="sdk_gphone64_x86_64",
            model="sdk_gphone64_x86_64",
            device="emu64xa",
            connection_type=AdbConnectionType.SOCKET,
            negotiated_speed=480_000_000,
            max_speed=480_000_000,
            transport_id=17,
        )

        self.assertEqual(device.state, AdbConnectionState.DEVICE)
        self.assertEqual(device.connection_type, AdbConnectionType.SOCKET)
        self.assertEqual(device.transport_id, AdbTransportId(17))

    def test_missing_tracker_fields_use_proto_defaults(self) -> None:
        device = AdbTrackedDevice(
            serial="device-1",
            state=AdbConnectionState.OFFLINE,
        )

        self.assertEqual(device.connection_type, AdbConnectionType.UNKNOWN)
        self.assertEqual(device.transport_id, 0)
        self.assertEqual(device.product, "")

    def test_snapshot_is_a_tuple_of_tracked_devices(self) -> None:
        device = AdbTrackedDevice(serial="device-1", state=AdbConnectionState.DEVICE)
        snapshot = AdbDevicesSnapshot((device,))
        self.assertEqual(snapshot.devices, (device,))

        with self.assertRaisesRegex(TypeError, "devices must be a tuple"):
            AdbDevicesSnapshot([device])  # type: ignore[arg-type]


class AdbServerStatusTests(unittest.TestCase):
    def test_endpoint_defaults_to_standard_smart_socket(self) -> None:
        self.assertEqual(AdbServerEndpoint(), AdbServerEndpoint("localhost", 5037))

    def test_server_status_matches_aosp_payload_vocabulary(self) -> None:
        status = AdbServerStatus(
            usb_backend=AdbUsbBackend.LIBUSB,
            usb_backend_forced=True,
            mdns_backend=AdbMdnsBackend.OPENSCREEN,
            mdns_backend_forced=False,
            version="35.0.2",
            build="android-build",
            executable_absolute_path="/opt/android/adb",
            log_absolute_path="/tmp/adb.log",
            os="linux",
            trace_level="sockets",
            burst_mode=True,
            mdns_enabled=False,
        )

        self.assertEqual(status.usb_backend, AdbUsbBackend.LIBUSB)
        self.assertEqual(status.mdns_backend, AdbMdnsBackend.OPENSCREEN)
        self.assertEqual(status.version, "35.0.2")
        self.assertTrue(status.burst_mode)

    def test_unknown_server_proto_enums_are_preserved_as_raw_integers(self) -> None:
        status = AdbServerStatus(usb_backend=77, mdns_backend=88)

        self.assertEqual(status.usb_backend, 77)
        self.assertIs(type(status.usb_backend), int)
        self.assertEqual(status.mdns_backend, 88)
        self.assertIs(type(status.mdns_backend), int)


if __name__ == "__main__":
    unittest.main()
