from __future__ import annotations

import unittest

from adb._internal.proto import parse_server_status
from adb.server.status.adapters import SmartSocketAdbServerStatusReader
from adb.transport.devices.adapters import SmartSocketAdbDevicesSnapshotReader
from adb.transport.adapters import SmartSocketAdbTransportFeaturesReader
from adb.server import AdbMdnsBackend, AdbServerEndpoint, AdbUsbBackend
from adb.transport import AdbTransportId


def _varint(value: int) -> bytes:
    output = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            output.append(byte | 0x80)
        else:
            output.append(byte)
            return bytes(output)


def _field_varint(number: int, value: int) -> bytes:
    return _varint(number << 3) + _varint(value)


def _field_bytes(number: int, value: bytes) -> bytes:
    return _varint((number << 3) | 2) + _varint(len(value)) + value


def _device_payload(serial: str, transport_id: int) -> bytes:
    return _field_bytes(1, serial.encode()) + _field_varint(10, transport_id)


class _FakeClient:
    def __init__(self, *, host_payload: bytes = b"", stream_payload: bytes = b"") -> None:
        self.host_payload = host_payload
        self.stream_payload = stream_payload
        self.host_services: list[str] = []
        self.stream_services: list[str] = []
        self.feature_selectors: list[object] = []
        self.feature_values = frozenset({"shell_v2", "cmd"})

    def host_query(self, service: str) -> bytes:
        self.host_services.append(service)
        return self.host_payload

    def first_stream_frame(self, service: str) -> bytes:
        self.stream_services.append(service)
        return self.stream_payload

    def features(self, selector) -> frozenset[str]:
        self.feature_selectors.append(selector)
        return self.feature_values


class AdbNativeAdapterTests(unittest.TestCase):
    def test_server_status_proto_is_decoded_without_protobuf_runtime(self) -> None:
        payload = b"".join(
            (
                _field_varint(1, 2),
                _field_varint(2, 1),
                _field_varint(3, 2),
                _field_bytes(5, b"36.0.0"),
                _field_bytes(9, b"linux"),
                _field_varint(12, 1),
            )
        )
        status = parse_server_status(payload)

        self.assertEqual(status.usb_backend, AdbUsbBackend.LIBUSB)
        self.assertTrue(status.usb_backend_forced)
        self.assertEqual(status.mdns_backend, AdbMdnsBackend.OPENSCREEN)
        self.assertEqual(status.version, "36.0.0")
        self.assertTrue(status.mdns_enabled)

    def test_server_status_reader_uses_host_server_status(self) -> None:
        fake = _FakeClient(host_payload=_field_bytes(5, b"36.0.0"))
        reader = SmartSocketAdbServerStatusReader(_client_factory=lambda endpoint: fake)

        status = reader.read(AdbServerEndpoint())

        self.assertEqual(status.version, "36.0.0")
        self.assertEqual(fake.host_services, ["host:server-status"])

    def test_devices_snapshot_reader_reads_first_complete_tracker_snapshot(self) -> None:
        device = _device_payload("device-1", 27)
        snapshot_payload = _field_bytes(1, device)
        fake = _FakeClient(stream_payload=snapshot_payload)
        reader = SmartSocketAdbDevicesSnapshotReader(_client_factory=lambda endpoint: fake)

        snapshot = reader.read(AdbServerEndpoint())

        self.assertEqual(snapshot.devices[0].serial, "device-1")
        self.assertEqual(snapshot.devices[0].transport_id, AdbTransportId(27))
        self.assertEqual(fake.stream_services, ["host:track-devices-proto-binary"])

    def test_transport_features_are_public_open_fact(self) -> None:
        from adb.transport import AdbDeviceSerial, AdbTransportBySerial

        fake = _FakeClient()
        selector = AdbTransportBySerial(AdbDeviceSerial("device-1"))
        reader = SmartSocketAdbTransportFeaturesReader(
            _client_factory=lambda endpoint: fake
        )

        features = reader.read(AdbServerEndpoint(), selector)

        self.assertIn("shell_v2", features)
        self.assertIn("cmd", features)
        self.assertEqual(fake.feature_selectors, [selector])


if __name__ == "__main__":
    unittest.main()
