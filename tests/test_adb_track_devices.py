from __future__ import annotations

from collections.abc import Iterator
import math
import socket
from threading import Event, Thread
import unittest
from unittest.mock import patch

from adb.transport.observation.source import AdbTrackDevicesSource
from adb.transport.devices import (
    AdbConnectionState,
    AdbConnectionType,
    AdbDevicesSnapshot,
)
from adb.transport.observation import (
    AdbObservationProtocolError,
    AdbObservationServerConnectionError,
    AdbObservationServiceError,
)
from adb.server import AdbServerEndpoint


def _frame(payload: bytes) -> bytes:
    return f"{len(payload):04x}".encode("ascii") + payload


def _varint(value: int) -> bytes:
    if value < 0:
        value &= (1 << 64) - 1
    encoded = bytearray()
    while value >= 0x80:
        encoded.append((value & 0x7F) | 0x80)
        value >>= 7
    encoded.append(value)
    return bytes(encoded)


def _varint_field(field_number: int, value: int) -> bytes:
    return _varint(field_number << 3) + _varint(value)


def _bytes_field(field_number: int, value: bytes) -> bytes:
    return _varint((field_number << 3) | 2) + _varint(len(value)) + value


def _text_field(field_number: int, value: str) -> bytes:
    return _bytes_field(field_number, value.encode("utf-8"))


def _device(
    *,
    serial: str = "",
    state: int = 0,
    bus_address: str = "",
    product: str = "",
    model: str = "",
    device: str = "",
    connection_type: int = 0,
    negotiated_speed: int = 0,
    max_speed: int = 0,
    transport_id: int = 0,
    extra: bytes = b"",
) -> bytes:
    payload = bytearray()
    if serial:
        payload += _text_field(1, serial)
    if state:
        payload += _varint_field(2, state)
    if bus_address:
        payload += _text_field(3, bus_address)
    if product:
        payload += _text_field(4, product)
    if model:
        payload += _text_field(5, model)
    if device:
        payload += _text_field(6, device)
    if connection_type:
        payload += _varint_field(7, connection_type)
    if negotiated_speed:
        payload += _varint_field(8, negotiated_speed)
    if max_speed:
        payload += _varint_field(9, max_speed)
    if transport_id:
        payload += _varint_field(10, transport_id)
    payload += extra
    return bytes(payload)


def _devices(*devices: bytes, extra: bytes = b"") -> bytes:
    return b"".join(_bytes_field(1, device) for device in devices) + extra


class _FakeSocket:
    def __init__(
        self,
        incoming: bytes = b"",
        *,
        recv_chunks: tuple[int, ...] = (),
        connect_error: OSError | None = None,
    ) -> None:
        self.incoming = bytearray(incoming)
        self.recv_chunks = iter(recv_chunks)
        self.connect_error = connect_error
        self.sent = bytearray()
        self.timeouts: list[float | None] = []
        self.closed = False
        self.shutdown_calls = 0
        self.close_calls = 0

    def settimeout(self, value: float | None) -> None:
        self.timeouts.append(value)

    def connect(self, sockaddr: object) -> None:
        del sockaddr
        if self.connect_error is not None:
            raise self.connect_error

    def sendall(self, data: bytes) -> None:
        self.sent.extend(data)

    def recv(self, size: int) -> bytes:
        if self.closed or not self.incoming:
            return b""
        try:
            chunk_size = next(self.recv_chunks)
        except StopIteration:
            chunk_size = size
        count = min(size, chunk_size, len(self.incoming))
        data = bytes(self.incoming[:count])
        del self.incoming[:count]
        return data

    def shutdown(self, how: int) -> None:
        del how
        self.shutdown_calls += 1
        self.closed = True

    def close(self) -> None:
        self.close_calls += 1
        self.closed = True


class _BlockingReadSocket(_FakeSocket):
    def __init__(self, incoming: bytes = b"OKAY") -> None:
        super().__init__(incoming)
        self.blocked = Event()
        self.released = Event()

    def recv(self, size: int) -> bytes:
        if self.incoming:
            return super().recv(size)
        self.blocked.set()
        self.released.wait(2)
        return b""

    def shutdown(self, how: int) -> None:
        super().shutdown(how)
        self.released.set()

    def close(self) -> None:
        super().close()
        self.released.set()


class _BlockingConnectSocket(_FakeSocket):
    def __init__(self) -> None:
        super().__init__()
        self.started = Event()
        self.released = Event()

    def connect(self, sockaddr: object) -> None:
        del sockaddr
        self.started.set()
        self.released.wait(2)
        if self.closed:
            raise OSError("closed during connect")

    def shutdown(self, how: int) -> None:
        super().shutdown(how)
        self.released.set()

    def close(self) -> None:
        super().close()
        self.released.set()


class _SocketFactory:
    def __init__(self, *sockets: _FakeSocket) -> None:
        self.sockets: Iterator[_FakeSocket] = iter(sockets)

    def __call__(self, family: int, socktype: int, proto: int) -> _FakeSocket:
        del family, socktype, proto
        return next(self.sockets)


def _address_info():
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 5037))]


class AdbTrackDevicesTests(unittest.TestCase):
    def _patch_socket(self, *sockets: _FakeSocket):
        return (
            patch(
                "adb.transport.observation.source.socket.getaddrinfo",
                return_value=_address_info(),
            ),
            patch(
                "adb.transport.observation.source.socket.socket",
                side_effect=_SocketFactory(*sockets),
            ),
        )

    def _consume_session(self, source: AdbTrackDevicesSource) -> tuple[AdbDevicesSnapshot, ...]:
        session = source.open()
        self.assertIsNotNone(session)
        assert session is not None
        try:
            return tuple(session.snapshots())
        finally:
            session.close()

    def _collect_to_eof(self, source: AdbTrackDevicesSource):
        snapshots: list[AdbDevicesSnapshot] = []
        session = source.open()
        self.assertIsNotNone(session)
        assert session is not None
        try:
            with self.assertRaises(AdbObservationServerConnectionError):
                for snapshot in session.snapshots():
                    self.assertIsInstance(snapshot, AdbDevicesSnapshot)
                    snapshots.append(snapshot)
        finally:
            session.close()
        return snapshots

    def test_public_models_validate_endpoint_and_timeout(self) -> None:
        self.assertEqual(AdbServerEndpoint(), AdbServerEndpoint("localhost", 5037))
        self.assertEqual(AdbServerEndpoint(" host ", 5555).host, "host")
        with self.assertRaises(ValueError):
            AdbServerEndpoint(host=" ")
        for port in (True, 5037.0, "5037"):
            with self.subTest(port=port):
                with self.assertRaises(TypeError):
                    AdbServerEndpoint(port=port)  # type: ignore[arg-type]
        for port in (0, -1, 65536):
            with self.subTest(port=port):
                with self.assertRaises(ValueError):
                    AdbServerEndpoint(port=port)

        for timeout in (True, 0, -1, math.nan, math.inf, "5"):
            with self.subTest(timeout=timeout):
                with self.assertRaises((TypeError, ValueError)):
                    AdbTrackDevicesSource(
                        startup_timeout_seconds=timeout,  # type: ignore[arg-type]
                    )

    def test_fragmented_protocol_bootstrap_and_request_bytes(self) -> None:
        payload = _devices(
            _device(
                serial="z",
                state=AdbConnectionState.OFFLINE,
                bus_address="1-2",
                product="pixel",
                model="Pixel_8",
                device="shiba",
                connection_type=AdbConnectionType.USB,
                negotiated_speed=480,
                max_speed=5000,
                transport_id=17,
            ),
            _device(
                serial="a",
                state=AdbConnectionState.DEVICE,
                connection_type=AdbConnectionType.SOCKET,
                transport_id=22,
            ),
        )
        sock = _FakeSocket(
            b"OKAY" + _frame(payload),
            recv_chunks=(1, 1, 2, 1, 3, 2, 4, 5, 20, 40, 80),
        )
        getaddr_patch, socket_patch = self._patch_socket(sock)
        source = AdbTrackDevicesSource()

        with getaddr_patch, socket_patch:
            snapshots = self._collect_to_eof(source)

        self.assertEqual(
            bytes(sock.sent),
            b"001fhost:track-devices-proto-binary",
        )
        self.assertEqual(len(snapshots), 1)
        first, second = snapshots[0].devices
        self.assertEqual((first.serial, first.state), ("z", AdbConnectionState.OFFLINE))
        self.assertEqual(first.connection_type, AdbConnectionType.USB)
        self.assertEqual(first.bus_address, "1-2")
        self.assertEqual(first.product, "pixel")
        self.assertEqual(first.model, "Pixel_8")
        self.assertEqual(first.device, "shiba")
        self.assertEqual(first.negotiated_speed, 480)
        self.assertEqual(first.max_speed, 5000)
        self.assertEqual(first.transport_id, 17)
        self.assertEqual(second.connection_type, AdbConnectionType.SOCKET)
        self.assertEqual(second.transport_id, 22)

    def test_tracker_yields_complete_snapshots_without_diffing(self) -> None:
        first = _devices(
            _device(serial="b", state=AdbConnectionState.DEVICE, transport_id=17),
            _device(serial="a", state=AdbConnectionState.OFFLINE, transport_id=18),
        )
        second = _devices(
            _device(serial="a", state=AdbConnectionState.DEVICE, transport_id=18),
            _device(serial="d", state=AdbConnectionState.UNAUTHORIZED, transport_id=22),
        )
        sock = _FakeSocket(b"OKAY" + _frame(first) + _frame(second) + _frame(b""))
        getaddr_patch, socket_patch = self._patch_socket(sock)

        with getaddr_patch, socket_patch:
            snapshots = self._collect_to_eof(AdbTrackDevicesSource())

        self.assertEqual(len(snapshots), 3)
        self.assertEqual([d.serial for d in snapshots[0].devices], ["b", "a"])
        self.assertEqual([d.serial for d in snapshots[1].devices], ["a", "d"])
        self.assertEqual(snapshots[2], AdbDevicesSnapshot())

    def test_proto_defaults_and_duplicate_rows_are_preserved(self) -> None:
        payload = _devices(
            _device(serial="same"),
            _device(serial="same", state=AdbConnectionState.DEVICE),
        )
        sock = _FakeSocket(b"OKAY" + _frame(payload))
        getaddr_patch, socket_patch = self._patch_socket(sock)
        with getaddr_patch, socket_patch:
            snapshots = self._collect_to_eof(AdbTrackDevicesSource())

        first, second = snapshots[0].devices
        self.assertEqual(first.serial, "same")
        self.assertEqual(first.state, AdbConnectionState.ANY)
        self.assertEqual(first.connection_type, AdbConnectionType.UNKNOWN)
        self.assertEqual(first.transport_id, 0)
        self.assertEqual(second.serial, "same")
        self.assertEqual(second.state, AdbConnectionState.DEVICE)

    def test_unknown_enum_and_unknown_fields_remain_forward_compatible(self) -> None:
        payload = _devices(
            _device(
                serial="future",
                state=77,
                connection_type=99,
                transport_id=31,
                extra=_varint_field(99, 1234) + _bytes_field(100, b"future"),
            ),
            extra=_bytes_field(2, b"ignored"),
        )
        sock = _FakeSocket(b"OKAY" + _frame(payload))
        getaddr_patch, socket_patch = self._patch_socket(sock)

        with getaddr_patch, socket_patch:
            snapshots = self._collect_to_eof(AdbTrackDevicesSource())

        device = snapshots[0].devices[0]
        self.assertEqual(device.state, 77)
        self.assertIs(type(device.state), int)
        self.assertEqual(device.connection_type, 99)
        self.assertIs(type(device.connection_type), int)
        self.assertEqual(device.transport_id, 31)

    def test_repeated_singular_proto_fields_use_last_value(self) -> None:
        repeated = (
            _text_field(1, "first")
            + _text_field(1, "last")
            + _varint_field(2, AdbConnectionState.OFFLINE)
            + _varint_field(2, AdbConnectionState.DEVICE)
        )
        sock = _FakeSocket(b"OKAY" + _frame(_devices(repeated)))
        getaddr_patch, socket_patch = self._patch_socket(sock)

        with getaddr_patch, socket_patch:
            snapshots = self._collect_to_eof(AdbTrackDevicesSource())

        device = snapshots[0].devices[0]
        self.assertEqual(device.serial, "last")
        self.assertEqual(device.state, AdbConnectionState.DEVICE)

    def test_invalid_snapshot_is_atomic_and_protocol_typed(self) -> None:
        payloads = (
            b"\x0a\x80",
            _devices(b"\x08\x01"),
            _devices(_bytes_field(1, b"\xff")),
            b"\x08\x01",
            _devices(b"\x10\x80"),
            _devices(b"\x13"),
        )
        for payload in payloads:
            with self.subTest(payload=payload):
                sock = _FakeSocket(b"OKAY" + _frame(payload))
                getaddr_patch, socket_patch = self._patch_socket(sock)
                with getaddr_patch, socket_patch:
                    with self.assertRaises(AdbObservationProtocolError):
                        self._consume_session(AdbTrackDevicesSource())

    def test_service_and_framing_failures_are_typed(self) -> None:
        cases = (
            (b"FAIL" + _frame(b"unavailable"), AdbObservationServiceError),
            (b"FAILzzzz", AdbObservationProtocolError),
            (b"OKAYzzzz", AdbObservationProtocolError),
        )
        for incoming, error_type in cases:
            with self.subTest(error_type=error_type):
                sock = _FakeSocket(incoming)
                getaddr_patch, socket_patch = self._patch_socket(sock)
                with getaddr_patch, socket_patch:
                    with self.assertRaises(error_type):
                        self._consume_session(AdbTrackDevicesSource())

    def test_server_connection_failure_and_eof_remain_observation_failures(self) -> None:
        failed = _FakeSocket(connect_error=OSError("refused"))
        getaddr_patch, socket_patch = self._patch_socket(failed)
        with getaddr_patch, socket_patch:
            with self.assertRaises(AdbObservationServerConnectionError):
                self._consume_session(AdbTrackDevicesSource())

        payload = _devices(_device(serial="device-1", state=AdbConnectionState.DEVICE))
        sock = _FakeSocket(b"OKAY" + _frame(payload))
        getaddr_patch, socket_patch = self._patch_socket(sock)
        with getaddr_patch, socket_patch:
            snapshots = self._collect_to_eof(AdbTrackDevicesSource())
        self.assertEqual(len(snapshots), 1)

    def test_startup_timeout_is_one_post_resolution_monotonic_deadline(self) -> None:
        sock = _FakeSocket(b"OKAY" + _frame(b""))
        getaddr_patch, socket_patch = self._patch_socket(sock)
        source = AdbTrackDevicesSource(startup_timeout_seconds=5.0)
        ticks = iter((100.0, 101.0, 102.0, 103.0, 104.0))

        with getaddr_patch, socket_patch, patch(
            "adb.transport.observation.source.monotonic",
            side_effect=lambda: next(ticks),
        ):
            with self.assertRaises(AdbObservationServerConnectionError):
                self._consume_session(source)

        finite = [value for value in sock.timeouts if value is not None]
        self.assertEqual(finite[:3], [4.0, 3.0, 2.0])

    def test_close_is_idempotent_interrupts_blocked_read_and_exhausts_future_sessions(self) -> None:
        sock = _BlockingReadSocket()
        getaddr_patch, socket_patch = self._patch_socket(sock)
        source = AdbTrackDevicesSource()
        result: list[object] = []

        with getaddr_patch, socket_patch:
            session = source.open()
            self.assertIsNotNone(session)
            assert session is not None
            iterator = session.snapshots()

            def consume() -> None:
                try:
                    result.append(next(iterator))
                except StopIteration:
                    result.append("stopped")

            thread = Thread(target=consume)
            thread.start()
            self.assertTrue(sock.blocked.wait(1))
            source.close()
            source.close()
            thread.join(2)

        self.assertEqual(result, ["stopped"])
        self.assertIsNone(source.open())
        self.assertGreaterEqual(sock.shutdown_calls, 1)

    def test_concurrent_consumption_is_rejected_until_session_failure_cleans_up(self) -> None:
        sock = _BlockingReadSocket()
        getaddr_patch, socket_patch = self._patch_socket(sock)
        source = AdbTrackDevicesSource()
        result: list[object] = []

        with getaddr_patch, socket_patch:
            first_session = source.open()
            self.assertIsNotNone(first_session)
            assert first_session is not None
            first = first_session.snapshots()

            def consume() -> None:
                try:
                    result.append(next(first))
                except Exception as exc:  # pragma: no cover - assertion below checks type
                    result.append(exc)

            thread = Thread(target=consume)
            thread.start()
            self.assertTrue(sock.blocked.wait(1))
            with self.assertRaisesRegex(RuntimeError, "already active"):
                source.open()
            source.close()
            thread.join(2)

        self.assertEqual(len(result), 1)


if __name__ == "__main__":
    unittest.main()
