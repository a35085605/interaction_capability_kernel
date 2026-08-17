from __future__ import annotations

import time
import unittest

from adb.configuration import (
    AdbServerConfiguration,
    AdbServerId,
    AdbTransportBindingId,
)
from adb.server.endpoint import AdbServerEndpoint
from adb.supervision import (
    AdbTransportBindingRecoveryExhausted,
    AdbTransportBindingResolutionChanged,
    AdbTransportBindingSupervisionPolicy,
    AdbTransportBindingSupervisor,
)
from adb.transport.binding import (
    AdbTransportBindingConfiguration,
    AdbTransportBindingResolutionStatus,
)
from adb.transport.inventory.domain import (
    AdbConnectionState,
    AdbDevicesSnapshot,
    AdbTrackedDevice,
)
from adb.transport.observation.contracts import AdbObservationSessionId
from adb.transport.observation.signal import (
    AdbTransportInventoryObservationStarted,
    AdbTransportInventorySnapshotObserved,
)
from adb.transport.orchestration import (
    AdbTransportPreparationPolicy,
    AdbTransportPreparationResult,
    AdbTransportPreparationStatus,
)
from adb.transport.selection import AdbDeviceSerial, AdbTransportBySerial
from eventing.models import EventSubscriptionToken


class _Bus:
    def __init__(self) -> None:
        self.handlers: dict[str, tuple[type, object]] = {}
        self.counter = 0

    def subscribe(self, event_type, handler):
        self.counter += 1
        token = EventSubscriptionToken(f"sub-{self.counter}")
        self.handlers[token.value] = (event_type, handler)
        return token

    def unsubscribe(self, token):
        return self.handlers.pop(token.value, None) is not None

    def publish(self, event):
        for event_type, handler in list(self.handlers.values()):
            if isinstance(event, event_type):
                handler(event)


class _Observation:
    def __init__(self, session_id: AdbObservationSessionId) -> None:
        self.current_session_id = session_id

    def start(self):
        return self.current_session_id

    def stop(self):
        pass

    def close(self):
        pass


class _SnapshotReader:
    def __init__(self, snapshot: AdbDevicesSnapshot) -> None:
        self.snapshot = snapshot

    def read(self, endpoint):
        return self.snapshot


class _Preparation:
    def __init__(self, result_factory) -> None:
        self.result_factory = result_factory
        self.calls = []

    def prepare(self, operation, policy):
        self.calls.append((operation, policy))
        return self.result_factory(operation, policy)


def _wait_until(predicate, timeout_seconds: float = 1.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while not predicate():
        if time.monotonic() >= deadline:
            raise AssertionError("timed out waiting for binding recovery")
        time.sleep(0.005)


def _server() -> AdbServerConfiguration:
    return AdbServerConfiguration(
        AdbServerId("local"),
        AdbServerEndpoint("127.0.0.1", 5037),
    )


def _binding(serial: str = "target") -> AdbTransportBindingConfiguration:
    return AdbTransportBindingConfiguration(
        _server().server_id,
        AdbTransportBindingId("primary"),
        AdbTransportBySerial(AdbDeviceSerial(serial)),
        "192.0.2.10:5555",
    )


def _snapshot(*serials: str) -> AdbDevicesSnapshot:
    return AdbDevicesSnapshot(
        tuple(
            AdbTrackedDevice(serial=serial, state=AdbConnectionState.DEVICE)
            for serial in serials
        )
    )


class AdbTransportBindingSupervisorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bus = _Bus()
        self.session = AdbObservationSessionId(_server().server_id, 1)
        self.observation = _Observation(self.session)

    def test_registered_binding_projects_only_its_selector_from_full_inventory(self) -> None:
        reader = _SnapshotReader(_snapshot("other-a", "target", "other-b"))
        supervisor = AdbTransportBindingSupervisor(
            _server(), self.bus, self.observation, reader, lambda config: None
        )
        changes: list[AdbTransportBindingResolutionChanged] = []
        self.bus.subscribe(AdbTransportBindingResolutionChanged, changes.append)
        supervisor.start()

        supervisor.register(_binding())

        resolution = supervisor.resolution(_binding().binding_id)
        self.assertIsNotNone(resolution)
        self.assertIs(resolution.status, AdbTransportBindingResolutionStatus.RESOLVED)
        self.assertEqual(resolution.row.serial, "target")
        self.assertEqual(len(changes), 1)
        self.assertIsNone(changes[0].previous)
        self.assertEqual(changes[0].current.matches, (resolution.row,))

    def test_absent_binding_runs_one_bounded_recovery_and_emits_exhausted(self) -> None:
        absent = _snapshot("other-a", "other-b")
        reader = _SnapshotReader(absent)
        preparation_policy = AdbTransportPreparationPolicy(
            0.1,
            frozenset({AdbConnectionState.DEVICE}),
        )

        def result_factory(operation, policy):
            return AdbTransportPreparationResult(
                operation=operation,
                policy=policy,
                status=AdbTransportPreparationStatus.TIMED_OUT,
                satisfaction=None,
                presence_satisfaction=None,
                observation_session_id=self.session,
                attempts=(),
                final_snapshot=absent,
            )

        preparation = _Preparation(result_factory)
        supervisor = AdbTransportBindingSupervisor(
            _server(),
            self.bus,
            self.observation,
            reader,
            lambda config: preparation,
        )
        exhausted: list[AdbTransportBindingRecoveryExhausted] = []
        self.bus.subscribe(AdbTransportBindingRecoveryExhausted, exhausted.append)
        supervisor.start()

        supervisor.register(
            _binding(),
            AdbTransportBindingSupervisionPolicy(preparation_policy),
        )
        _wait_until(lambda: len(exhausted) == 1)

        self.assertEqual(len(preparation.calls), 1)
        self.assertEqual(exhausted[0].configuration.binding_id, _binding().binding_id)
        self.assertIs(exhausted[0].result.status, AdbTransportPreparationStatus.TIMED_OUT)

        self.bus.publish(
            AdbTransportInventorySnapshotObserved(_server().endpoint, self.session, absent)
        )
        time.sleep(0.02)
        self.assertEqual(len(preparation.calls), 1)

    def test_resolution_change_rearms_recovery_for_a_new_absence_episode(self) -> None:
        absent = _snapshot("other")
        present = _snapshot("target")
        reader = _SnapshotReader(absent)
        preparation_policy = AdbTransportPreparationPolicy(
            0.1,
            frozenset({AdbConnectionState.DEVICE}),
        )

        def result_factory(operation, policy):
            return AdbTransportPreparationResult(
                operation=operation,
                policy=policy,
                status=AdbTransportPreparationStatus.TIMED_OUT,
                satisfaction=None,
                presence_satisfaction=None,
                observation_session_id=self.session,
                attempts=(),
                final_snapshot=absent,
            )

        preparation = _Preparation(result_factory)
        supervisor = AdbTransportBindingSupervisor(
            _server(), self.bus, self.observation, reader, lambda config: preparation
        )
        supervisor.start()
        supervisor.register(
            _binding(),
            AdbTransportBindingSupervisionPolicy(preparation_policy),
        )
        _wait_until(lambda: len(preparation.calls) == 1)

        self.bus.publish(
            AdbTransportInventorySnapshotObserved(_server().endpoint, self.session, present)
        )
        self.bus.publish(
            AdbTransportInventorySnapshotObserved(_server().endpoint, self.session, absent)
        )
        _wait_until(lambda: len(preparation.calls) == 2)

    def test_new_observation_generation_establishes_a_new_binding_baseline(self) -> None:
        reader = _SnapshotReader(_snapshot("target"))
        supervisor = AdbTransportBindingSupervisor(
            _server(), self.bus, self.observation, reader, lambda config: None
        )
        changes: list[AdbTransportBindingResolutionChanged] = []
        self.bus.subscribe(AdbTransportBindingResolutionChanged, changes.append)
        supervisor.start()
        supervisor.register(_binding())

        next_session = AdbObservationSessionId(_server().server_id, 2)
        self.observation.current_session_id = next_session
        self.bus.publish(
            AdbTransportInventoryObservationStarted(_server().endpoint, next_session)
        )
        self.bus.publish(
            AdbTransportInventorySnapshotObserved(
                _server().endpoint, next_session, _snapshot("target")
            )
        )

        self.assertEqual(len(changes), 2)
        self.assertIsNone(changes[1].previous)
        self.assertEqual(changes[1].session_id, next_session)


if __name__ == "__main__":
    unittest.main()
