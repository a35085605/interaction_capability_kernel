from __future__ import annotations

import time
import unittest

from adb.server.endpoint import AdbServerEndpoint
from adb.supervision import (
    AdbTransportBindingRecoveryExhausted,
    AdbTransportBindingResolutionChanged,
    AdbTransportBindingSupervisionPolicy,
    AdbTransportBindingSupervisor,
)
from adb.transport.binding import AdbTransportBindingConfiguration, AdbTransportBindingResolutionStatus
from adb.transport.devices.domain import AdbConnectionState, AdbDevicesSnapshot, AdbTrackedDevice
from adb.transport.observation.contracts import AdbObservationSessionId
from adb.transport.observation.signal import AdbDevicesObservationStarted, AdbDevicesSnapshotObserved
from adb.transport.orchestration import AdbTransportPreparationPolicy, AdbTransportPreparationResult, AdbTransportPreparationStatus
from adb.transport.selection import AdbDeviceSerial
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
        self.active_session_id = session_id

    def start(self):
        return self.active_session_id

    def stop(self):
        self.active_session_id = None

    def close(self):
        self.active_session_id = None


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


def _endpoint() -> AdbServerEndpoint:
    return AdbServerEndpoint("127.0.0.1", 5037)


def _binding(serial: str = "target") -> AdbTransportBindingConfiguration:
    return AdbTransportBindingConfiguration(
        _endpoint(), AdbDeviceSerial(serial), "192.0.2.10:5555"
    )


def _snapshot(*serials: str) -> AdbDevicesSnapshot:
    return AdbDevicesSnapshot(
        tuple(AdbTrackedDevice(serial=serial, state=AdbConnectionState.DEVICE) for serial in serials)
    )


class AdbTransportBindingSupervisorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bus = _Bus()
        self.session = AdbObservationSessionId(_endpoint(), 1)
        self.observation = _Observation(self.session)

    def test_registered_binding_projects_only_its_serial_from_full_inventory(self) -> None:
        reader = _SnapshotReader(_snapshot("other-a", "target", "other-b"))
        supervisor = AdbTransportBindingSupervisor(
            _endpoint(), self.bus, self.observation, reader, lambda config: None
        )
        changes: list[AdbTransportBindingResolutionChanged] = []
        self.bus.subscribe(AdbTransportBindingResolutionChanged, changes.append)
        supervisor.start()
        supervisor.register(_binding())
        resolution = supervisor.resolution(_binding().serial)
        self.assertIsNotNone(resolution)
        self.assertIs(resolution.status, AdbTransportBindingResolutionStatus.RESOLVED)
        self.assertEqual(resolution.row.serial, "target")
        self.assertEqual(len(changes), 1)
        self.assertIsNone(changes[0].previous)
        self.assertEqual(changes[0].current.matches, (resolution.row,))

    def test_serial_is_the_registration_identity(self) -> None:
        reader = _SnapshotReader(_snapshot("target"))
        supervisor = AdbTransportBindingSupervisor(
            _endpoint(), self.bus, self.observation, reader, lambda config: None
        )
        supervisor.start()
        supervisor.register(_binding())
        with self.assertRaisesRegex(ValueError, "already registered"):
            supervisor.register(
                AdbTransportBindingConfiguration(
                    _endpoint(), AdbDeviceSerial("target"), "192.0.2.99:5555"
                )
            )

    def test_binding_endpoint_must_match_supervisor_endpoint(self) -> None:
        reader = _SnapshotReader(_snapshot("target"))
        supervisor = AdbTransportBindingSupervisor(
            _endpoint(), self.bus, self.observation, reader, lambda config: None
        )
        supervisor.start()
        with self.assertRaisesRegex(ValueError, "endpoint"):
            supervisor.register(
                AdbTransportBindingConfiguration(
                    AdbServerEndpoint("127.0.0.1", 5040), AdbDeviceSerial("target")
                )
            )

    def test_absent_binding_runs_one_bounded_recovery_and_emits_exhausted(self) -> None:
        absent = _snapshot("other-a", "other-b")
        reader = _SnapshotReader(absent)
        preparation_policy = AdbTransportPreparationPolicy(0.1, frozenset({AdbConnectionState.DEVICE}))

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
            _endpoint(), self.bus, self.observation, reader, lambda config: preparation
        )
        exhausted: list[AdbTransportBindingRecoveryExhausted] = []
        self.bus.subscribe(AdbTransportBindingRecoveryExhausted, exhausted.append)
        supervisor.start()
        supervisor.register(_binding(), AdbTransportBindingSupervisionPolicy(preparation_policy))
        _wait_until(lambda: len(exhausted) == 1)
        self.assertEqual(len(preparation.calls), 1)
        self.assertEqual(exhausted[0].configuration.serial, _binding().serial)
        self.assertIs(exhausted[0].result.status, AdbTransportPreparationStatus.TIMED_OUT)
        self.bus.publish(AdbDevicesSnapshotObserved(_endpoint(), self.session, absent))
        time.sleep(0.02)
        self.assertEqual(len(preparation.calls), 1)

    def test_resolution_change_rearms_recovery_for_a_new_absence_episode(self) -> None:
        absent = _snapshot("other")
        present = _snapshot("target")
        reader = _SnapshotReader(absent)
        preparation_policy = AdbTransportPreparationPolicy(0.1, frozenset({AdbConnectionState.DEVICE}))

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
            _endpoint(), self.bus, self.observation, reader, lambda config: preparation
        )
        supervisor.start()
        supervisor.register(_binding(), AdbTransportBindingSupervisionPolicy(preparation_policy))
        _wait_until(lambda: len(preparation.calls) == 1)
        self.bus.publish(AdbDevicesSnapshotObserved(_endpoint(), self.session, present))
        self.bus.publish(AdbDevicesSnapshotObserved(_endpoint(), self.session, absent))
        _wait_until(lambda: len(preparation.calls) == 2)

    def test_new_observation_generation_establishes_a_new_binding_baseline(self) -> None:
        reader = _SnapshotReader(_snapshot("target"))
        supervisor = AdbTransportBindingSupervisor(
            _endpoint(), self.bus, self.observation, reader, lambda config: None
        )
        changes: list[AdbTransportBindingResolutionChanged] = []
        self.bus.subscribe(AdbTransportBindingResolutionChanged, changes.append)
        supervisor.start()
        supervisor.register(_binding())
        next_session = AdbObservationSessionId(_endpoint(), 2)
        self.observation.active_session_id = next_session
        self.bus.publish(AdbDevicesObservationStarted(_endpoint(), next_session))
        self.bus.publish(AdbDevicesSnapshotObserved(_endpoint(), next_session, _snapshot("target")))
        self.assertEqual(len(changes), 2)
        self.assertIsNone(changes[1].previous)
        self.assertEqual(changes[1].session_id, next_session)

    def test_register_does_not_project_when_observation_is_inactive(self) -> None:
        reader = _SnapshotReader(_snapshot("target"))
        self.observation.active_session_id = None
        supervisor = AdbTransportBindingSupervisor(
            _endpoint(), self.bus, self.observation, reader, lambda config: None
        )
        supervisor.start()
        supervisor.register(_binding())
        self.assertIsNone(supervisor.resolution(_binding().serial))


if __name__ == "__main__":
    unittest.main()
