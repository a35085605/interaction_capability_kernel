from __future__ import annotations

import unittest

from adb._internal.client import ShellV2Result
from adb.errors import AdbTimeoutError
from adb.server import AdbServerEndpoint
from adb.transport import AdbDeviceSerial, AdbTransportBySerial
from android.adb.adapters.command import AdbActivityLauncher, AdbPackageForceStopper
from android.identity import AndroidComponentName, AndroidPackageName, AndroidUserId
from android.command import AndroidActivityLaunch, AndroidPackageForceStop
from native_attempt import NativeAttemptStatus, NativeCompletionScope


class _FakeClient:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.commands: list[str] = []

    def shell_v2(self, selector, command: str) -> ShellV2Result:
        self.commands.append(command)
        if self.error is not None:
            raise self.error
        return ShellV2Result(stdout=b"Starting: Intent {}\n", stderr=b"", exit_code=0)


class AndroidAdbCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.endpoint = AdbServerEndpoint()
        self.selector = AdbTransportBySerial(AdbDeviceSerial("device-1"))
        self.user = AndroidUserId(10)
        self.package = AndroidPackageName("com.example")

    def test_launch_and_force_stop_are_user_scoped_typed_attempts(self) -> None:
        fake = _FakeClient()
        launch = AdbActivityLauncher(
            self.endpoint,
            self.selector,
            _client_factory=lambda endpoint: fake,
        )
        force_stop = AdbPackageForceStopper(
            self.endpoint,
            self.selector,
            _client_factory=lambda endpoint: fake,
        )

        launch_result = launch.launch(
            AndroidActivityLaunch(
                self.user,
                AndroidComponentName(self.package, ".MainActivity"),
            )
        )
        stop_result = force_stop.force_stop(AndroidPackageForceStop(self.user, self.package))

        self.assertEqual(
            fake.commands,
            [
                "am start --user 10 -n com.example/.MainActivity",
                "am force-stop --user 10 com.example",
            ],
        )
        self.assertIs(launch_result.status, NativeAttemptStatus.SUCCEEDED)
        self.assertIs(launch_result.completion_scope, NativeCompletionScope.PROCESS_EXIT)
        self.assertIs(stop_result.status, NativeAttemptStatus.SUCCEEDED)

    def test_command_timeout_is_timed_out_with_unknown_completion_scope(self) -> None:
        fake = _FakeClient(error=AdbTimeoutError("read timed out"))
        launch = AdbActivityLauncher(
            self.endpoint,
            self.selector,
            _client_factory=lambda endpoint: fake,
        )

        result = launch.launch(
            AndroidActivityLaunch(
                self.user,
                AndroidComponentName(self.package, ".MainActivity"),
            )
        )

        self.assertIs(result.status, NativeAttemptStatus.TIMED_OUT)
        self.assertIsNone(result.completion_scope)


if __name__ == "__main__":
    unittest.main()
