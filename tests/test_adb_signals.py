from __future__ import annotations

from datetime import datetime, timezone
import unittest

from adb.configuration import AdbServerConfiguration, AdbServerId
from adb.server import AdbServerEndpoint, AdbServerStatus
from adb.server.lifecycle import (
    AdbServerAvailability,
    AdbServerEnsureAvailable,
    AdbServerEnsurePolicy,
    AdbServerEnsureResult,
    AdbServerEnsureStatus,
    AdbServerProbeResult,
    AdbServerSatisfaction,
    AdbServerStart,
)
from adb.server.signal import (
    AdbServerCommandCompleted,
    AdbServerEnsureCompleted,
    AdbServerProbeCompleted,
)
from adb.transport.observation.contracts import AdbObservationSessionId
from adb.transport.inventory.domain import AdbDevicesSnapshot
from adb.transport.observation import signal as observation_signal
from adb.transport.observation.signal import (
    AdbTransportInventoryObservationFailed,
    AdbTransportInventoryObservationFailure,
    AdbTransportInventoryObservationStarted,
    AdbTransportInventoryObservationStopped,
    AdbTransportInventorySnapshotObserved,
)
from adb.transport.connection import AdbTransportReconnect
from adb.transport.selection import AdbDeviceSerial, AdbTransportBySerial
from adb.transport.signal import AdbTransportCommandCompleted
from native_attempt import (
    NativeAttemptResult,
    NativeAttemptStatus,
    NativeCompletionScope,
)


def _successful_attempt() -> NativeAttemptResult:
    now = datetime(2026, 8, 16, tzinfo=timezone.utc)
    return NativeAttemptResult(
        status=NativeAttemptStatus.SUCCEEDED,
        completion_scope=NativeCompletionScope.PROCESS_EXIT,
        backend_id="test-adb",
        started_at=now,
        finished_at=now,
        native_code="0",
    )


class AdbServerSignalTests(unittest.TestCase):
    def test_atomic_command_completion_preserves_operation_and_attempt(self) -> None:
        operation = AdbServerStart(AdbServerId("local-main"))
        attempt = _successful_attempt()

        signal = AdbServerCommandCompleted(operation, attempt)

        self.assertIs(signal.operation, operation)
        self.assertIs(signal.result, attempt)

    def test_probe_and_ensure_completion_preserve_domain_evidence(self) -> None:
        configuration = AdbServerConfiguration(
            AdbServerId("local-main"),
            AdbServerEndpoint(),
        )
        probe = AdbServerProbeResult(
            configuration=configuration,
            availability=AdbServerAvailability.AVAILABLE,
            server_status=AdbServerStatus(version="0010"),
        )
        operation = AdbServerEnsureAvailable(
            configuration.server_id,
            AdbServerEnsurePolicy(5, 0.25),
        )
        result = AdbServerEnsureResult(
            operation=operation,
            status=AdbServerEnsureStatus.SATISFIED,
            satisfaction=AdbServerSatisfaction.ALREADY_SATISFIED,
            attempts=(),
            final_probe=probe,
        )

        self.assertIs(AdbServerProbeCompleted(probe).probe, probe)
        self.assertIs(AdbServerEnsureCompleted(result).result, result)


class AdbTransportInventorySignalTests(unittest.TestCase):
    def test_observation_session_signals_carry_endpoint_and_session_identity(self) -> None:
        endpoint = AdbServerEndpoint("127.0.0.1", 5037)
        session_id = AdbObservationSessionId(AdbServerId("local-main"), 1)

        self.assertIs(
            AdbTransportInventoryObservationStarted(endpoint, session_id).endpoint,
            endpoint,
        )
        self.assertIs(
            AdbTransportInventoryObservationStopped(endpoint, session_id).endpoint,
            endpoint,
        )
        failed = AdbTransportInventoryObservationFailed(
            endpoint,
            session_id,
            AdbTransportInventoryObservationFailure.SERVER_CONNECTION,
            " socket lost ",
        )
        self.assertEqual(failed.diagnostic, "socket lost")
        self.assertEqual(failed.failure.value, "server_connection")

    def test_snapshot_signal_preserves_complete_native_inventory_fact(self) -> None:
        endpoint = AdbServerEndpoint()
        session_id = AdbObservationSessionId(AdbServerId("local-main"), 1)
        snapshot = AdbDevicesSnapshot()

        signal = AdbTransportInventorySnapshotObserved(endpoint, session_id, snapshot)

        self.assertIs(signal.snapshot, snapshot)

    def test_observation_signal_module_does_not_expose_row_lifecycle_vocabulary(self) -> None:
        for name in (
            "AdbTrackedDeviceAppeared",
            "AdbTrackedDeviceChanged",
            "AdbTrackedDeviceDisappeared",
            "AdbTrackedDeviceSignal",
        ):
            with self.subTest(name=name):
                self.assertFalse(hasattr(observation_signal, name))


class AdbTransportSignalTests(unittest.TestCase):
    def test_atomic_command_completion_preserves_operation_and_attempt(self) -> None:
        operation = AdbTransportReconnect(
            AdbTransportBySerial(AdbDeviceSerial("device-1"))
        )
        attempt = _successful_attempt()

        signal = AdbTransportCommandCompleted(operation, attempt)

        self.assertIs(signal.operation, operation)
        self.assertIs(signal.result, attempt)


if __name__ == "__main__":
    unittest.main()
