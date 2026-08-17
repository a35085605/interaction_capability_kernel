from __future__ import annotations

import struct
import unittest

from adb._internal.client import AdbServiceClient
from adb.errors import (
    AdbServerConnectionError,
    AdbTimeoutError,
    AdbTransportNotFoundError,
)
from adb.server import AdbServerEndpoint
from adb.transport import (
    AdbDeviceSerial,
    AdbTransportById,
    AdbTransportBySerial,
    AdbTransportId,
)


def _protocol_string(payload: bytes) -> bytes:
    return f"{len(payload):04x}".encode("ascii") + payload


def _shell_packet(packet_id: int, payload: bytes) -> bytes:
    return bytes([packet_id]) + struct.pack("<I", len(payload)) + payload


class _FakeSocket:
    def __init__(self, incoming: bytes, *, fragment: int = 2) -> None:
        self.incoming = bytearray(incoming)
        self.fragment = fragment
        self.sent: list[bytes] = []
        self.timeout = None
        self.closed = False

    def settimeout(self, value) -> None:
        self.timeout = value

    def sendall(self, data: bytes) -> None:
        self.sent.append(data)

    def recv(self, size: int) -> bytes:
        if not self.incoming:
            return b""
        count = min(size, self.fragment, len(self.incoming))
        data = bytes(self.incoming[:count])
        del self.incoming[:count]
        return data

    def close(self) -> None:
        self.closed = True


class AdbServiceClientTests(unittest.TestCase):
    def test_timeout_is_typed_as_server_connection_failure(self) -> None:
        self.assertTrue(issubclass(AdbTimeoutError, AdbServerConnectionError))

    def test_host_query_uses_smart_socket_framing(self) -> None:
        sock = _FakeSocket(b"OKAY" + _protocol_string(b"abc"))
        client = AdbServiceClient(
            AdbServerEndpoint(),
            _socket_factory=lambda *args, **kwargs: sock,
        )

        self.assertEqual(client.host_query("host:test"), b"abc")
        self.assertEqual(sock.sent, [b"0009host:test"])
        self.assertTrue(sock.closed)

    def test_shell_v2_selects_serial_and_preserves_stream_channels(self) -> None:
        incoming = (
            b"OKAY"
            + b"OKAY"
            + _shell_packet(1, b"out")
            + _shell_packet(2, b"err")
            + _shell_packet(3, b"\x07")
        )
        sock = _FakeSocket(incoming, fragment=1)
        client = AdbServiceClient(
            AdbServerEndpoint(),
            _socket_factory=lambda *args, **kwargs: sock,
        )

        result = client.shell_v2(
            AdbTransportBySerial(AdbDeviceSerial("device-1")),
            "echo ok",
        )

        self.assertEqual(result.stdout, b"out")
        self.assertEqual(result.stderr, b"err")
        self.assertEqual(result.exit_code, 7)
        self.assertEqual(sock.sent[0], b"0017host:transport:device-1")
        self.assertEqual(sock.sent[1], b"0014shell,v2,raw:echo ok")

    def test_raw_exec_can_select_server_local_transport_id(self) -> None:
        sock = _FakeSocket(b"OKAYOKAY\x89PNGraw", fragment=3)
        client = AdbServiceClient(
            AdbServerEndpoint(),
            _socket_factory=lambda *args, **kwargs: sock,
        )

        payload = client.raw_exec(
            AdbTransportById(AdbTransportId(42)),
            "screencap -p",
        )

        self.assertEqual(payload, b"\x89PNGraw")
        self.assertEqual(sock.sent[0], b"0014host:transport-id:42")

    def test_transport_fail_is_classified(self) -> None:
        detail = b"device not found"
        sock = _FakeSocket(b"FAIL" + _protocol_string(detail))
        client = AdbServiceClient(
            AdbServerEndpoint(),
            _socket_factory=lambda *args, **kwargs: sock,
        )

        with self.assertRaises(AdbTransportNotFoundError):
            client.raw_exec(
                AdbTransportBySerial(AdbDeviceSerial("missing")),
                "true",
            )

    def test_feature_query_uses_typed_transport_prefix(self) -> None:
        sock = _FakeSocket(b"OKAY" + _protocol_string(b"shell_v2,cmd"))
        client = AdbServiceClient(
            AdbServerEndpoint(),
            _socket_factory=lambda *args, **kwargs: sock,
        )

        features = client.features(AdbTransportById(AdbTransportId(5)))

        self.assertEqual(features, frozenset({"shell_v2", "cmd"}))
        self.assertEqual(sock.sent, [b"001chost-transport-id:5:features"])


if __name__ == "__main__":
    unittest.main()
