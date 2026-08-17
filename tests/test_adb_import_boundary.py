from __future__ import annotations

import importlib.util
import subprocess
import sys
import unittest


class AdbImportBoundaryTests(unittest.TestCase):
    def test_adb_root_does_not_load_android_display_integration(self) -> None:
        script = """
import sys
import adb

assert hasattr(adb, 'AdbServerConnectionError')
assert not hasattr(adb, 'AdbConnectionError')
assert hasattr(adb, 'AdbServerStatusReader')
assert hasattr(adb, 'AdbDevicesSnapshotReader')
assert hasattr(adb, 'AdbTrackedDeviceLookup')
assert 'android' not in sys.modules
assert 'geometry' not in sys.modules
"""
        subprocess.run([sys.executable, "-c", script], check=True)

    def test_canonical_adb_ownership_slices_are_public(self) -> None:
        for namespace in (
            "adb.server",
            "adb.server.status",
            "adb.server.lifecycle",
            "adb.transport",
            "adb.transport.connection",
            "adb.transport.inventory",
            "adb.transport.observation",
            "adb.transport.orchestration",
            "adb.server.signal",
            "adb.transport.signal",
            "adb.transport.observation.signal",
        ):
            with self.subTest(namespace=namespace):
                self.assertIsNotNone(importlib.util.find_spec(namespace))

    def test_legacy_adb_compatibility_modules_are_absent(self) -> None:
        for namespace in (
            "adb.server.adapters",
            "adb.server.command",
            "adb.server.domain",
            "adb.server.orchestration",
            "adb.server.query",
            "adb.transport.command",
        ):
            with self.subTest(namespace=namespace):
                self.assertIsNone(importlib.util.find_spec(namespace))


if __name__ == "__main__":
    unittest.main()
