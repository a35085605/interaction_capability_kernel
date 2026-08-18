from __future__ import annotations

import inspect
import unittest

from adb.server.status.query import AdbServerStatusReader
from adb.transport.devices.query import AdbDevicesSnapshotReader, AdbTrackedDeviceLookup
from adb.transport.query import AdbTransportFeaturesReader
from android.adb.query import (
    AdbBootStateInspector,
    AdbDisplayInspector,
    AdbDisplaysInspector,
    AdbKeyguardStateInspector,
    AdbPackageStateInspector,
    AdbPhysicalDisplaysInspector,
    AdbPowerStateInspector,
    AdbResumedActivitiesInspector,
    AdbUserStateInspector,
)
from windows.query import DesktopInspector, WindowInspector


class NativeInspectorContractTests(unittest.TestCase):
    def test_desktop_inspection_is_target_free(self) -> None:
        parameters = tuple(inspect.signature(DesktopInspector.inspect).parameters)
        self.assertEqual(parameters, ("self",))

    def test_window_inspection_is_keyed_by_window_identity(self) -> None:
        parameters = tuple(inspect.signature(WindowInspector.inspect).parameters)
        self.assertEqual(parameters, ("self", "window_id"))

    def test_adb_host_readers_are_keyed_by_native_server_transport_identity(self) -> None:
        self.assertEqual(
            tuple(inspect.signature(AdbServerStatusReader.read).parameters),
            ("self", "endpoint"),
        )
        self.assertEqual(
            tuple(inspect.signature(AdbDevicesSnapshotReader.read).parameters),
            ("self", "endpoint"),
        )
        self.assertEqual(
            tuple(inspect.signature(AdbTrackedDeviceLookup.find).parameters),
            ("self", "endpoint", "selector"),
        )
        self.assertEqual(
            tuple(inspect.signature(AdbTransportFeaturesReader.read).parameters),
            ("self", "endpoint", "selector"),
        )

    def test_android_queries_are_scoped_only_by_android_and_adb_native_identity(self) -> None:
        expected = {
            AdbBootStateInspector: ("self", "endpoint", "selector"),
            AdbDisplaysInspector: ("self", "endpoint", "selector"),
            AdbDisplayInspector: ("self", "endpoint", "selector", "display_id"),
            AdbPhysicalDisplaysInspector: ("self", "endpoint", "selector"),
            AdbUserStateInspector: ("self", "endpoint", "selector", "user_id"),
            AdbPackageStateInspector: (
                "self",
                "endpoint",
                "selector",
                "user_id",
                "package_name",
            ),
            AdbResumedActivitiesInspector: ("self", "endpoint", "selector"),
            AdbPowerStateInspector: ("self", "endpoint", "selector"),
            AdbKeyguardStateInspector: ("self", "endpoint", "selector"),
        }
        for inspector, parameters in expected.items():
            with self.subTest(inspector=inspector.__name__):
                self.assertEqual(
                    tuple(inspect.signature(inspector.inspect).parameters),
                    parameters,
                )


if __name__ == "__main__":
    unittest.main()
