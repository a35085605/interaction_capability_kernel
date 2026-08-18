from __future__ import annotations

from datetime import datetime, timezone
import subprocess
import unittest
from unittest.mock import patch

from adb.pairing.adapters import SubprocessAdbPairing
from adb.pairing.command import AdbWirelessPair
from adb.server.lifecycle import (
    AdbServerAvailability,
    AdbServerEnsureAvailable,
    AdbServerEnsurePolicy,
    AdbServerEnsureResult,
    AdbServerEnsureStatus,
    AdbServerEnsureUnavailable,
    AdbServerProbeResult,
    AdbServerSatisfaction,
    AdbServerStart,
    AdbServerStarter,
    AdbServerStop,
    AdbServerStopper,
)
from adb.server.lifecycle.adapters import SubprocessAdbServer
from adb.transport.connection import (
    AdbDeviceSideReconnect,
    AdbOfflineTransportsReconnect,
    AdbTcpConnect,
    AdbTcpDisconnect,
    AdbTransportReconnect,
)
from adb.transport.orchestration import AdbTransportPreparation, AdbTransportRecovery
from adb.transport.connection.adapters import SubprocessAdbTransport
from adb.transport import (
    AdbDeviceSerial,
    AdbTransportById,
    AdbTransportBySerial,
    AdbTransportId,
)
from adb.server import AdbServerEndpoint, AdbServerStatus
from native_attempt import NativeAttemptResult, NativeAttemptStatus, NativeCompletionScope


def _server_endpoint(*, host: str = "localhost", port: int = 5037) -> AdbServerEndpoint:
    return AdbServerEndpoint(host, port)


def _successful_attempt() -> NativeAttemptResult:
    now = datetime(2026, 8, 16, tzinfo=timezone.utc)
    return NativeAttemptResult(
        status=NativeAttemptStatus.SUCCEEDED,
        completion_scope=NativeCompletionScope.PROCESS_EXIT,
        backend_id="adb-subprocess",
        started_at=now,
        finished_at=now,
        native_code="0",
    )


class AdbServerCommandAndOrchestrationVocabularyTests(unittest.TestCase):
    def test_atomic_server_commands_are_keyed_by_native_endpoint(self) -> None:
        endpoint = _server_endpoint()

        self.assertIs(AdbServerStart(endpoint).endpoint, endpoint)
        self.assertIs(AdbServerStop(endpoint).endpoint, endpoint)

        with self.assertRaisesRegex(TypeError, "AdbServerEndpoint"):
            AdbServerStart("local-main")  # type: ignore[arg-type]

    def test_ensure_operations_keep_waiting_policy_explicit(self) -> None:
        endpoint = _server_endpoint()
        policy = AdbServerEnsurePolicy(timeout_seconds=5, probe_interval_seconds=0.25)

        available = AdbServerEnsureAvailable(endpoint, policy)
        unavailable = AdbServerEnsureUnavailable(endpoint, policy)

        self.assertIs(available.endpoint, endpoint)
        self.assertIs(available.policy, policy)
        self.assertIs(unavailable.endpoint, endpoint)
        self.assertEqual(policy.timeout_seconds, 5.0)
        self.assertEqual(policy.probe_interval_seconds, 0.25)

    def test_ensure_policy_rejects_non_positive_or_non_finite_durations(self) -> None:
        with self.assertRaisesRegex(ValueError, "timeout"):
            AdbServerEnsurePolicy(0, 0.1)
        with self.assertRaisesRegex(ValueError, "probe interval"):
            AdbServerEnsurePolicy(1, float("inf"))

    def test_available_probe_requires_native_server_status(self) -> None:
        endpoint = _server_endpoint()
        server_status = AdbServerStatus(version="0010")
        probe = AdbServerProbeResult(
            endpoint=endpoint,
            availability=AdbServerAvailability.AVAILABLE,
            server_status=server_status,
        )
        self.assertIs(probe.server_status, server_status)
        with self.assertRaisesRegex(ValueError, "requires AdbServerStatus"):
            AdbServerProbeResult(endpoint, AdbServerAvailability.AVAILABLE)

    def test_unavailable_probe_does_not_synthesize_server_status(self) -> None:
        endpoint = _server_endpoint()
        probe = AdbServerProbeResult(
            endpoint=endpoint,
            availability=AdbServerAvailability.UNAVAILABLE,
            diagnostic="connection refused",
        )
        self.assertIsNone(probe.server_status)
        self.assertEqual(probe.diagnostic, "connection refused")
        with self.assertRaisesRegex(ValueError, "cannot carry AdbServerStatus"):
            AdbServerProbeResult(
                endpoint,
                AdbServerAvailability.UNAVAILABLE,
                server_status=AdbServerStatus(),
            )

    def test_already_available_result_contains_no_native_attempt(self) -> None:
        endpoint = _server_endpoint()
        operation = AdbServerEnsureAvailable(endpoint, AdbServerEnsurePolicy(5, 0.1))
        final_probe = AdbServerProbeResult(
            endpoint=endpoint,
            availability=AdbServerAvailability.AVAILABLE,
            server_status=AdbServerStatus(),
        )
        result = AdbServerEnsureResult(
            operation=operation,
            status=AdbServerEnsureStatus.SATISFIED,
            satisfaction=AdbServerSatisfaction.ALREADY_SATISFIED,
            attempts=(),
            final_probe=final_probe,
        )
        self.assertEqual(result.attempts, ())

    def test_achieved_unavailability_can_preserve_atomic_stop_evidence(self) -> None:
        endpoint = _server_endpoint()
        operation = AdbServerEnsureUnavailable(endpoint, AdbServerEnsurePolicy(5, 0.1))
        attempt = _successful_attempt()
        result = AdbServerEnsureResult(
            operation=operation,
            status=AdbServerEnsureStatus.SATISFIED,
            satisfaction=AdbServerSatisfaction.ACHIEVED,
            attempts=(attempt,),
            final_probe=AdbServerProbeResult(endpoint, AdbServerAvailability.UNAVAILABLE),
        )
        self.assertEqual(result.attempts, (attempt,))

    def test_unsatisfied_result_cannot_claim_matching_final_probe(self) -> None:
        endpoint = _server_endpoint()
        operation = AdbServerEnsureAvailable(endpoint, AdbServerEnsurePolicy(5, 0.1))
        with self.assertRaisesRegex(ValueError, "matching final probe"):
            AdbServerEnsureResult(
                operation=operation,
                status=AdbServerEnsureStatus.TIMED_OUT,
                satisfaction=None,
                attempts=(_successful_attempt(),),
                final_probe=AdbServerProbeResult(
                    endpoint,
                    AdbServerAvailability.AVAILABLE,
                    server_status=AdbServerStatus(),
                ),
            )


class AdbServerLifecyclePortTests(unittest.TestCase):
    def test_subprocess_adapter_satisfies_explicit_server_lifecycle_ports(self) -> None:
        server = SubprocessAdbServer(_server_endpoint())
        starter: AdbServerStarter = server
        stopper: AdbServerStopper = server
        self.assertTrue(callable(starter.start))
        self.assertTrue(callable(stopper.stop))


class SubprocessAdbServerTests(unittest.TestCase):
    @patch("adb._internal.subprocess.subprocess.run")
    def test_start_targets_native_server_endpoint(self, run) -> None:
        run.return_value = subprocess.CompletedProcess(args=["adb", "start-server"], returncode=0, stdout="", stderr="")
        endpoint = _server_endpoint(host="127.0.0.1", port=5040)
        result = SubprocessAdbServer(endpoint).start(AdbServerStart(endpoint))
        run.assert_called_once_with(
            ["adb", "-H", "127.0.0.1", "-P", "5040", "start-server"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10.0,
        )
        self.assertIs(result.status, NativeAttemptStatus.SUCCEEDED)
        self.assertIs(result.completion_scope, NativeCompletionScope.PROCESS_EXIT)

    @patch("adb._internal.subprocess.subprocess.run")
    def test_stop_targets_native_server_endpoint(self, run) -> None:
        run.return_value = subprocess.CompletedProcess(args=["custom-adb", "kill-server"], returncode=0, stdout="", stderr="")
        endpoint = _server_endpoint(port=5040)
        SubprocessAdbServer(endpoint, executable="custom-adb").stop(AdbServerStop(endpoint))
        run.assert_called_once_with(
            ["custom-adb", "-H", "localhost", "-P", "5040", "kill-server"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10.0,
        )

    @patch("adb._internal.subprocess.subprocess.run")
    def test_server_operation_must_match_adapter_endpoint(self, run) -> None:
        endpoint = _server_endpoint()
        with self.assertRaisesRegex(ValueError, "does not match"):
            SubprocessAdbServer(endpoint).start(AdbServerStart(_server_endpoint(port=5040)))
        run.assert_not_called()

    @patch("adb._internal.subprocess.subprocess.run")
    def test_native_failure_is_reported(self, run) -> None:
        run.return_value = subprocess.CompletedProcess(args=["adb", "start-server"], returncode=1, stdout="", stderr="cannot connect to daemon")
        endpoint = _server_endpoint()
        result = SubprocessAdbServer(endpoint).start(AdbServerStart(endpoint))
        self.assertIs(result.status, NativeAttemptStatus.FAILED)
        self.assertIs(result.completion_scope, NativeCompletionScope.PROCESS_EXIT)
        self.assertEqual(result.native_code, "1")
        self.assertEqual(result.diagnostic, "cannot connect to daemon")

    @patch("adb._internal.subprocess.subprocess.run")
    def test_process_start_failure_has_no_completion_scope(self, run) -> None:
        run.side_effect = FileNotFoundError("adb not found")
        endpoint = _server_endpoint()
        result = SubprocessAdbServer(endpoint).start(AdbServerStart(endpoint))
        self.assertIs(result.status, NativeAttemptStatus.FAILED)
        self.assertIsNone(result.completion_scope)
        self.assertEqual(result.native_code, "FileNotFoundError")

    @patch("adb._internal.subprocess.subprocess.run")
    def test_timeout_is_reported_as_timed_out(self, run) -> None:
        run.side_effect = subprocess.TimeoutExpired(["adb", "start-server"], timeout=2.0)
        endpoint = _server_endpoint()
        result = SubprocessAdbServer(endpoint, timeout_seconds=2).start(AdbServerStart(endpoint))
        self.assertIs(result.status, NativeAttemptStatus.TIMED_OUT)
        self.assertIsNone(result.completion_scope)
        self.assertEqual(result.native_code, "TimeoutExpired")


class AdbTransportOrchestrationVocabularyTests(unittest.TestCase):
    def test_transport_orchestration_uses_endpoint_and_serial_identity(self) -> None:
        endpoint = _server_endpoint()
        serial = AdbDeviceSerial("device-1")
        preparation = AdbTransportPreparation(endpoint=endpoint, serial=serial)
        recovery = AdbTransportRecovery(endpoint=endpoint, serial=serial)
        self.assertIs(preparation.endpoint, endpoint)
        self.assertIs(preparation.serial, serial)
        self.assertIs(recovery.endpoint, endpoint)
        self.assertIs(recovery.serial, serial)


class SubprocessAdbTransportTests(unittest.TestCase):
    @patch("adb._internal.subprocess.subprocess.run")
    def test_atomic_transport_commands_do_not_hide_retry_policy(self, run) -> None:
        run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="ok", stderr="")
        endpoint = _server_endpoint(host="127.0.0.1", port=5040)
        adapter = SubprocessAdbTransport(endpoint, timeout_seconds=3)
        serial = AdbTransportBySerial(AdbDeviceSerial("device-1"))
        transport_id = AdbTransportById(AdbTransportId(27))
        adapter.connect(AdbTcpConnect("192.0.2.10:5555"))
        adapter.disconnect(AdbTcpDisconnect("192.0.2.10:5555"))
        adapter.reconnect(AdbTransportReconnect(serial))
        adapter.reconnect_device(AdbDeviceSideReconnect(transport_id))
        adapter.reconnect_offline(AdbOfflineTransportsReconnect())
        self.assertEqual(
            [call.args[0] for call in run.call_args_list],
            [
                ["adb", "-H", "127.0.0.1", "-P", "5040", "connect", "192.0.2.10:5555"],
                ["adb", "-H", "127.0.0.1", "-P", "5040", "disconnect", "192.0.2.10:5555"],
                ["adb", "-H", "127.0.0.1", "-P", "5040", "-s", "device-1", "reconnect"],
                ["adb", "-H", "127.0.0.1", "-P", "5040", "-t", "27", "reconnect", "device"],
                ["adb", "-H", "127.0.0.1", "-P", "5040", "reconnect", "offline"],
            ],
        )
        self.assertTrue(all(call.kwargs["timeout"] == 3.0 for call in run.call_args_list))


class SubprocessAdbPairingTests(unittest.TestCase):
    @patch("adb._internal.subprocess.subprocess.run")
    def test_pairing_code_is_passed_via_stdin_not_argv(self, run) -> None:
        run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="paired", stderr="")
        endpoint = _server_endpoint(host="127.0.0.1", port=5040)
        SubprocessAdbPairing(endpoint).pair(AdbWirelessPair("192.0.2.20:37123", "123456"))
        args, kwargs = run.call_args
        self.assertEqual(args[0], ["adb", "-H", "127.0.0.1", "-P", "5040", "pair", "192.0.2.20:37123"])
        self.assertEqual(kwargs["input"], "123456\n")
        self.assertNotIn("123456", args[0])


if __name__ == "__main__":
    unittest.main()
