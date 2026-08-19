from __future__ import annotations

from threading import Event
import unittest

from adb.server import AdbServerEndpoint
from adb.transport.devices.domain import AdbDevicesSnapshot
from adb.transport.observation.contracts import AdbObservationServerConnectionError
from adb.transport.observation.observer import AdbDevicesObserver
from adb.transport.observation.signal import (
    AdbDevicesSnapshotObserved,
    AdbDevicesObservationFailed,
    AdbDevicesObservationStarted,
    AdbDevicesObservationStopped,
)
from adb.transport.observation.source import AdbTrackDevicesSource
from eventing.adapters import InMemoryEventBus


class _Session:
    def __init__(self, snapshots: tuple[AdbDevicesSnapshot, ...]) -> None:
        self._snapshots = snapshots
        self.closed = False

    def snapshots(self):
        yield from self._snapshots

    def close(self) -> None:
        self.closed = True


class _Source(AdbTrackDevicesSource):
    def __init__(self, endpoint: AdbServerEndpoint, *, fail: bool = False) -> None:
        super().__init__(endpoint)
        self.fail = fail
        self.session = _Session((AdbDevicesSnapshot(),))
        self.source_closed = False

    def open(self):
        if self.fail:
            raise AdbObservationServerConnectionError("connection lost")
        return self.session

    def close(self) -> None:
        self.source_closed = True


class AdbDevicesObserverTests(unittest.TestCase):
    def _endpoint(self) -> AdbServerEndpoint:
        return AdbServerEndpoint("127.0.0.1", 5037)

    def test_started_is_emitted_after_open_before_first_snapshot(self) -> None:
        bus = InMemoryEventBus()
        observed: list[object] = []
        active_when_started = []
        terminal = Event()

        observer = AdbDevicesObserver(
            self._endpoint(), bus, _source_factory=lambda endpoint: _Source(endpoint)
        )

        def collect(event: object) -> None:
            observed.append(event)
            if isinstance(event, AdbDevicesObservationStarted):
                active_when_started.append(observer.active_session_id)
            if isinstance(event, AdbDevicesObservationStopped):
                self.assertIsNone(observer.active_session_id)
                terminal.set()

        bus.subscribe(object, collect)
        session_id = observer.start()
        self.assertTrue(terminal.wait(2))
        self.assertIsInstance(observed[0], AdbDevicesObservationStarted)
        self.assertIsInstance(observed[1], AdbDevicesSnapshotObserved)
        self.assertIsInstance(observed[2], AdbDevicesObservationStopped)
        self.assertEqual(observed[0].session_id, session_id)
        self.assertEqual(active_when_started, [session_id])
        self.assertEqual(session_id.endpoint, self._endpoint())
        self.assertIsNone(observer.active_session_id)

    def test_server_connection_failure_is_generation_fenced_and_next_start_increments(self) -> None:
        bus = InMemoryEventBus()
        failures: list[AdbDevicesObservationFailed] = []
        terminal = Event()
        fail_next = [True, False]

        def source_factory(endpoint: AdbServerEndpoint) -> _Source:
            return _Source(endpoint, fail=fail_next.pop(0))

        observer = AdbDevicesObserver(
            self._endpoint(), bus, _source_factory=source_factory
        )

        def collect(event: AdbDevicesObservationFailed) -> None:
            failures.append(event)
            self.assertIsNone(observer.active_session_id)
            terminal.set()

        bus.subscribe(AdbDevicesObservationFailed, collect)
        first = observer.start()
        self.assertTrue(terminal.wait(2))
        self.assertIsNone(observer.active_session_id)

        second_terminal = Event()
        bus.subscribe(AdbDevicesObservationStopped, lambda event: second_terminal.set())
        second = observer.start()
        self.assertTrue(second_terminal.wait(2))
        self.assertEqual(first.generation, 1)
        self.assertEqual(second.generation, 2)
        self.assertEqual(failures[0].session_id, first)
        self.assertIsNone(observer.active_session_id)


if __name__ == "__main__":
    unittest.main()
