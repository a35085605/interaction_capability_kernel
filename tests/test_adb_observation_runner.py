from __future__ import annotations

from threading import Event
import unittest

from adb.configuration import AdbServerConfiguration, AdbServerId
from adb.server import AdbServerEndpoint
from adb.transport.inventory.domain import AdbDevicesSnapshot
from adb.transport.observation.contracts import AdbObservationServerConnectionError
from adb.transport.observation.runner import AdbTransportInventoryObservationRunner
from adb.transport.observation.signal import (
    AdbTransportInventorySnapshotObserved,
    AdbTransportInventoryObservationFailed,
    AdbTransportInventoryObservationStarted,
    AdbTransportInventoryObservationStopped,
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


class AdbObservationRunnerTests(unittest.TestCase):
    def _configuration(self) -> AdbServerConfiguration:
        return AdbServerConfiguration(
            AdbServerId("local-main"),
            AdbServerEndpoint("127.0.0.1", 5037),
        )

    def test_started_is_emitted_after_open_before_first_snapshot(self) -> None:
        bus = InMemoryEventBus()
        observed: list[object] = []
        terminal = Event()

        def collect(event: object) -> None:
            observed.append(event)
            if isinstance(event, AdbTransportInventoryObservationStopped):
                terminal.set()

        bus.subscribe(object, collect)
        runner = AdbTransportInventoryObservationRunner(
            self._configuration(),
            bus,
            _source_factory=lambda endpoint: _Source(endpoint),
        )

        session_id = runner.start()
        self.assertTrue(terminal.wait(2))

        self.assertIsInstance(observed[0], AdbTransportInventoryObservationStarted)
        self.assertIsInstance(observed[1], AdbTransportInventorySnapshotObserved)
        self.assertIsInstance(observed[2], AdbTransportInventoryObservationStopped)
        self.assertEqual(observed[0].session_id, session_id)
        self.assertEqual(observed[1].session_id, session_id)
        self.assertEqual(observed[2].session_id, session_id)

    def test_server_connection_failure_is_generation_fenced_and_next_start_increments(self) -> None:
        bus = InMemoryEventBus()
        failures: list[AdbTransportInventoryObservationFailed] = []
        terminal = Event()

        def collect(event: AdbTransportInventoryObservationFailed) -> None:
            failures.append(event)
            terminal.set()

        bus.subscribe(AdbTransportInventoryObservationFailed, collect)
        fail_next = [True, False]

        def source_factory(endpoint: AdbServerEndpoint) -> _Source:
            return _Source(endpoint, fail=fail_next.pop(0))

        runner = AdbTransportInventoryObservationRunner(
            self._configuration(),
            bus,
            _source_factory=source_factory,
        )

        first = runner.start()
        self.assertTrue(terminal.wait(2))
        second_terminal = Event()
        bus.subscribe(AdbTransportInventoryObservationStopped, lambda event: second_terminal.set())
        second = runner.start()
        self.assertTrue(second_terminal.wait(2))

        self.assertEqual(first.generation, 1)
        self.assertEqual(second.generation, 2)
        self.assertEqual(failures[0].session_id, first)


if __name__ == "__main__":
    unittest.main()
