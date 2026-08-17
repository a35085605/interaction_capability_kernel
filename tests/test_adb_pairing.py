from __future__ import annotations

from datetime import datetime, timezone
import subprocess
import unittest
from unittest.mock import patch

from adb.configuration import AdbServerConfiguration, AdbServerId
from adb.pairing.adapters import SubprocessAdbPairing
from adb.pairing.command import AdbWirelessPair
from adb.pairing.signal import AdbPairingCommandCompleted
from adb.server import AdbServerEndpoint
import adb.transport.connection.command as transport_command
from adb.transport.connection.adapters import SubprocessAdbTransport
from adb.transport.signal import AdbTransportCommandCompleted
from native_attempt import (
    NativeAttemptResult,
    NativeAttemptStatus,
    NativeCompletionScope,
)


def _configuration() -> AdbServerConfiguration:
    return AdbServerConfiguration(
        AdbServerId("local-main"),
        AdbServerEndpoint("127.0.0.1", 5040),
    )


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


class AdbPairingOwnershipTests(unittest.TestCase):
    def test_pairing_command_is_not_transport_owned(self) -> None:
        self.assertEqual(AdbWirelessPair.__module__, "adb.pairing.command")
        self.assertFalse(hasattr(transport_command, "AdbWirelessPair"))
        self.assertFalse(hasattr(SubprocessAdbTransport, "pair"))

    @patch("adb._internal.subprocess.subprocess.run")
    def test_pairing_code_is_passed_via_stdin_not_argv(self, run) -> None:
        run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="paired", stderr=""
        )

        SubprocessAdbPairing(_configuration()).pair(
            AdbWirelessPair("192.0.2.20:37123", "123456")
        )

        args, kwargs = run.call_args
        self.assertEqual(
            args[0],
            [
                "adb",
                "-H",
                "127.0.0.1",
                "-P",
                "5040",
                "pair",
                "192.0.2.20:37123",
            ],
        )
        self.assertEqual(kwargs["input"], "123456\n")
        self.assertNotIn("123456", args[0])

    def test_pairing_completion_signal_is_pairing_owned(self) -> None:
        operation = AdbWirelessPair("192.0.2.20:37123", "123456")
        attempt = _successful_attempt()

        signal = AdbPairingCommandCompleted(operation, attempt)

        self.assertIs(signal.operation, operation)
        self.assertIs(signal.result, attempt)
        with self.assertRaisesRegex(TypeError, "transport command"):
            AdbTransportCommandCompleted(operation, attempt)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
