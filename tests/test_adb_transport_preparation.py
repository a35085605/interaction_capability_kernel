from __future__ import annotations

from datetime import datetime, timezone
import unittest

from adb.configuration import AdbServerConfiguration, AdbServerId
from adb.server import AdbServerEndpoint
from adb.transport.binding import (
    AdbTransportBindingConfiguration,
    AdbTransportBindingResolutionStatus,
    resolve_transport_binding,
)
from adb.transport.connection import AdbTcpConnect
from adb.transport.inventory import (
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
    AdbTransportPreparation,
    AdbTransportPreparationPolicy,
    AdbTransportPreparationSatisfaction,
    AdbTransportPreparationStatus,
    AdbTransportPresenceSatisfaction,
)
from adb.transport.preparation import AdbTransportPreparationOrchestrator
from adb.transport.selection import AdbDeviceSerial, AdbTransportId
from adb.transport.signal import AdbTransportPreparationCompleted
from eventing.adapters import InMemoryEventBus
from native_attempt import (
    NativeAttemptResult,
    NativeAttemptStatus,
    NativeCompletionScope,
)


def _server_configuration() -> AdbServerConfiguration:
    return AdbServerConfiguration(
        AdbServerId("local-main"),
        AdbServerEndpoint("127.0.0.1", 5040),
    )


def _binding_configuration(*, connect_address: str | None = "192.0.2.10:5555"):
    return AdbTransportBindingConfiguration(
        server_id=AdbServerId("local-main"),
        serial=AdbDeviceSerial("device-1"),
        connect_address=connect_address,
    )


def _row(state: AdbConnectionState | int, transport_id: int = 27) -> AdbTrackedDevice:
    return AdbTrackedDevice(
        serial="device-1",
        state=state,
        transport_id=transport_id,
    )


def _attempt(status: NativeAttemptStatus = NativeAttemptStatus.SUCCEEDED) -> NativeAttemptResult:
    now = datetime(2026, 8, 17, tzinfo=timezone.utc)
    return NativeAttemptResult(
        status=status,
        completion_scope=NativeCompletionScope.PROCESS_EXIT,
        backend_id="test-adb",
        started_at=now,
        finished_at=now,
        native_code="0" if status is NativeAttemptStatus.SUCCEEDED else "1",
    )


class _SnapshotReader:
    def __init__(self, snapshot: AdbDevicesSnapshot) -> None:
        self.snapshot = snapshot
        self.calls = 0

    def read(self, endpoint: AdbServerEndpoint) -> AdbDevicesSnapshot:
        self.calls += 1
        return self.snapshot


class _Observation:
    def __init__(self, session_id: AdbObservationSessionId) -> None:
        self._session_id = session_id

    @property
    def current_session_id(self) -> AdbObservationSessionId | None:
        return self._session_id

    def start(self) -> AdbObservationSessionId:
        return self._session_id

    def stop(self) -> None:
        pass

    def close(self) -> None:
        pass


class _Connector:
    def __init__(
        self,
        result: NativeAttemptResult,
        after_connect=None,
    ) -> None:
        self.result = result
        self.after_connect = after_connect
        self.operations: list[AdbTcpConnect] = []

    def connect(self, operation: AdbTcpConnect) -> NativeAttemptResult:
        self.operations.append(operation)
        if self.after_connect is not None:
            self.after_connect()
        return self.result


class AdbTransportBindingResolutionTests(unittest.TestCase):
    def test_binding_resolution_is_presence_only_and_preserves_row_state(self) -> None:
        configuration = _binding_configuration()
        snapshot = AdbDevicesSnapshot((_row(AdbConnectionState.UNAUTHORIZED),))

        resolution = resolve_transport_binding(configuration, snapshot)

        self.assertIs(resolution.status, AdbTransportBindingResolutionStatus.RESOLVED)
        self.assertIs(resolution.row, snapshot.devices[0])
        self.assertIs(resolution.row.state, AdbConnectionState.UNAUTHORIZED)

    def test_binding_resolution_reports_absent_and_ambiguous(self) -> None:
        configuration = _binding_configuration()
        absent = resolve_transport_binding(configuration, AdbDevicesSnapshot())
        ambiguous = resolve_transport_binding(
            configuration,
            AdbDevicesSnapshot(
                (
                    _row(AdbConnectionState.OFFLINE, 27),
                    _row(AdbConnectionState.DEVICE, 31),
                )
            ),
        )

        self.assertIs(absent.status, AdbTransportBindingResolutionStatus.ABSENT)
        self.assertIs(ambiguous.status, AdbTransportBindingResolutionStatus.AMBIGUOUS)
        self.assertEqual(len(ambiguous.matches), 2)

    def test_binding_configuration_requires_serial_not_runtime_transport_id(self) -> None:
        with self.assertRaisesRegex(TypeError, "AdbDeviceSerial"):
            AdbTransportBindingConfiguration(
                server_id=AdbServerId("local-main"),
                serial=AdbTransportId(27),  # type: ignore[arg-type]
            )


class AdbTransportPreparationOrchestratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bus = InMemoryEventBus()
        self.session_id = AdbObservationSessionId(AdbServerId("local-main"), 7)
        self.observation = _Observation(self.session_id)
        self.operation = AdbTransportPreparation(
            AdbServerId("local-main"),
            AdbDeviceSerial("device-1"),
        )
        self.policy = AdbTransportPreparationPolicy(
            timeout_seconds=0.2,
            acceptable_states=frozenset({AdbConnectionState.DEVICE}),
            blocked_states=frozenset(
                {AdbConnectionState.UNAUTHORIZED, AdbConnectionState.NOPERMISSION}
            ),
        )

    def _orchestrator(self, snapshot: AdbDevicesSnapshot, connector: _Connector):
        return AdbTransportPreparationOrchestrator(
            _server_configuration(),
            _binding_configuration(),
            _SnapshotReader(snapshot),
            connector,
            self.bus,
            self.observation,
        )

    def _publish(self, snapshot: AdbDevicesSnapshot) -> None:
        self.bus.publish(
            AdbTransportInventorySnapshotObserved(
                _server_configuration().endpoint,
                self.session_id,
                snapshot,
            )
        )

    def test_already_ready_transport_skips_connect(self) -> None:
        connector = _Connector(_attempt())
        completed: list[AdbTransportPreparationCompleted] = []
        self.bus.subscribe(AdbTransportPreparationCompleted, completed.append)

        result = self._orchestrator(
            AdbDevicesSnapshot((_row(AdbConnectionState.DEVICE),)),
            connector,
        ).prepare(self.operation, self.policy)

        self.assertIs(result.status, AdbTransportPreparationStatus.SATISFIED)
        self.assertIs(
            result.satisfaction,
            AdbTransportPreparationSatisfaction.ALREADY_SATISFIED,
        )
        self.assertIs(
            result.presence_satisfaction,
            AdbTransportPresenceSatisfaction.ALREADY_PRESENT,
        )
        self.assertEqual(result.attempts, ())
        self.assertEqual(connector.operations, [])
        self.assertEqual(result.final_row.transport_id, AdbTransportId(27))
        self.assertIs(completed[-1].result, result)

    def test_presence_and_state_are_two_gates_inside_one_episode(self) -> None:
        def after_connect() -> None:
            self._publish(AdbDevicesSnapshot((_row(AdbConnectionState.OFFLINE),)))
            self._publish(AdbDevicesSnapshot((_row(AdbConnectionState.DEVICE),)))

        connector = _Connector(_attempt(), after_connect)
        result = self._orchestrator(AdbDevicesSnapshot(), connector).prepare(
            self.operation,
            self.policy,
        )

        self.assertIs(result.status, AdbTransportPreparationStatus.SATISFIED)
        self.assertIs(
            result.presence_satisfaction,
            AdbTransportPresenceSatisfaction.OBSERVED,
        )
        self.assertIs(result.final_row.state, AdbConnectionState.DEVICE)
        self.assertEqual(len(result.attempts), 1)
        self.assertEqual(connector.operations[0].address, "192.0.2.10:5555")
        self.assertIs(result.observation_session_id, self.session_id)

    def test_initial_presence_can_achieve_readiness_later_without_connect(self) -> None:
        connector = _Connector(_attempt())
        orchestrator = self._orchestrator(
            AdbDevicesSnapshot((_row(AdbConnectionState.OFFLINE),)),
            connector,
        )
        original_read = orchestrator._snapshot_reader.read

        def read_and_ready(endpoint):
            snapshot = original_read(endpoint)
            self._publish(AdbDevicesSnapshot((_row(AdbConnectionState.DEVICE),)))
            return snapshot

        orchestrator._snapshot_reader.read = read_and_ready  # type: ignore[method-assign]
        result = orchestrator.prepare(self.operation, self.policy)

        self.assertIs(result.status, AdbTransportPreparationStatus.SATISFIED)
        self.assertIs(
            result.satisfaction,
            AdbTransportPreparationSatisfaction.ACHIEVED,
        )
        self.assertIs(
            result.presence_satisfaction,
            AdbTransportPresenceSatisfaction.ALREADY_PRESENT,
        )
        self.assertEqual(connector.operations, [])

    def test_failed_connect_attempt_does_not_override_fresh_presence_evidence(self) -> None:
        def after_connect() -> None:
            self._publish(AdbDevicesSnapshot((_row(AdbConnectionState.DEVICE),)))

        failed_attempt = _attempt(NativeAttemptStatus.FAILED)
        connector = _Connector(failed_attempt, after_connect)

        result = self._orchestrator(AdbDevicesSnapshot(), connector).prepare(
            self.operation,
            self.policy,
        )

        self.assertIs(result.status, AdbTransportPreparationStatus.SATISFIED)
        self.assertEqual(result.attempts, (failed_attempt,))
        self.assertIs(
            result.satisfaction,
            AdbTransportPreparationSatisfaction.ACHIEVED,
        )

    def test_blocked_state_terminates_by_explicit_policy(self) -> None:
        connector = _Connector(_attempt())

        result = self._orchestrator(
            AdbDevicesSnapshot((_row(AdbConnectionState.UNAUTHORIZED),)),
            connector,
        ).prepare(self.operation, self.policy)

        self.assertIs(result.status, AdbTransportPreparationStatus.BLOCKED)
        self.assertIs(result.final_row.state, AdbConnectionState.UNAUTHORIZED)
        self.assertEqual(connector.operations, [])

    def test_serial_selected_preparation_follows_fresh_resolution(self) -> None:
        connector = _Connector(_attempt())
        orchestrator = self._orchestrator(
            AdbDevicesSnapshot((_row(AdbConnectionState.OFFLINE, 27),)),
            connector,
        )
        original_read = orchestrator._snapshot_reader.read

        def read_and_replace(endpoint):
            snapshot = original_read(endpoint)
            self._publish(AdbDevicesSnapshot())
            self._publish(AdbDevicesSnapshot((_row(AdbConnectionState.DEVICE, 31),)))
            return snapshot

        orchestrator._snapshot_reader.read = read_and_replace  # type: ignore[method-assign]
        result = orchestrator.prepare(self.operation, self.policy)

        self.assertIs(result.status, AdbTransportPreparationStatus.SATISFIED)
        self.assertIs(
            result.satisfaction,
            AdbTransportPreparationSatisfaction.ACHIEVED,
        )
        self.assertIs(
            result.presence_satisfaction,
            AdbTransportPresenceSatisfaction.ALREADY_PRESENT,
        )
        self.assertEqual(result.final_row.transport_id, AdbTransportId(31))
        self.assertEqual(connector.operations, [])

    def test_newer_observation_generation_terminates_episode(self) -> None:
        connector = _Connector(_attempt())
        orchestrator = self._orchestrator(AdbDevicesSnapshot(), connector)
        original_connect = connector.connect

        def connect_and_restart(operation):
            result = original_connect(operation)
            self.bus.publish(
                AdbTransportInventoryObservationStarted(
                    _server_configuration().endpoint,
                    AdbObservationSessionId(AdbServerId("local-main"), 8),
                )
            )
            return result

        connector.connect = connect_and_restart  # type: ignore[method-assign]
        result = orchestrator.prepare(self.operation, self.policy)

        self.assertIs(
            result.status,
            AdbTransportPreparationStatus.OBSERVATION_REPLACED,
        )


if __name__ == "__main__":
    unittest.main()
