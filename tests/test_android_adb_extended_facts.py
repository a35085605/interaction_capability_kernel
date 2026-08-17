from __future__ import annotations

from pathlib import Path
import unittest

from adb._internal.client import ShellV2Result
from adb.errors import AdbProtocolError
from adb.server import AdbServerEndpoint
from adb.transport import AdbDeviceSerial, AdbTransportBySerial
from android.adb.adapters.query import (
    SmartSocketAdbBuildInfoInspector,
    SmartSocketAdbCurrentUserInspector,
    SmartSocketAdbDisplayOcclusionsInspector,
    SmartSocketAdbLauncherActivityInspector,
    SmartSocketAdbUsersInspector,
    SmartSocketAdbWindowsInspector,
    parse_boot_completed,
    parse_build_info,
    parse_current_user,
    parse_display_occlusions,
    parse_launcher_component,
    parse_package_state,
    parse_resumed_activities,
    parse_users,
    parse_windows,
)
from android.application import AndroidPackageEnabledState
from android.display import AndroidDisplayId
from android.identity import AndroidPackageName, AndroidUserId
from android.runtime import AndroidBootState
from android.window import AndroidDisplayOcclusionKind, AndroidWindowViewVisibility
from geometry import Rect


_FIXTURES = Path(__file__).parent / "fixtures" / "android"


def _fixture(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


class _FakeClient:
    def __init__(self, stdout: str) -> None:
        self.stdout = stdout
        self.calls: list[tuple[object, str]] = []

    def shell_v2(self, selector, command: str) -> ShellV2Result:
        self.calls.append((selector, command))
        return ShellV2Result(stdout=self.stdout.encode(), stderr=b"", exit_code=0)


class StrictAndroidParserTests(unittest.TestCase):
    def test_boot_state_rejects_unknown_values(self) -> None:
        self.assertIs(parse_boot_completed("1\n"), AndroidBootState.BOOTED)
        self.assertIs(parse_boot_completed("0\n"), AndroidBootState.BOOTING)
        self.assertIs(parse_boot_completed("\n"), AndroidBootState.BOOTING)
        with self.assertRaisesRegex(AdbProtocolError, "sys.boot_completed"):
            parse_boot_completed("garbage\n")

    def test_display_snapshot_rejects_partial_candidate_parse(self) -> None:
        from android.adb.adapters.query import parse_dumpsys_display

        text = (
            'Display 0:\n'
            '  mBaseDisplayInfo=DisplayInfo{"ok", displayId 0, real 1080 x 2400, rotation 0, density 420 dpi}\n'
            'Display 7:\n'
            '  mBaseDisplayInfo=DisplayInfo{"changed", displayId 7}\n'
        )
        with self.assertRaisesRegex(AdbProtocolError, "supported Android display format"):
            parse_dumpsys_display(text)

    def test_resumed_activities_distinguishes_valid_empty_from_unparseable(self) -> None:
        self.assertEqual(
            parse_resumed_activities(_fixture("dumpsys_activity_empty.txt")).activities,
            (),
        )
        with self.assertRaisesRegex(AdbProtocolError, "activity activities format"):
            parse_resumed_activities("totally different output")
        with self.assertRaisesRegex(AdbProtocolError, "resumed-activity row"):
            parse_resumed_activities(
                "ACTIVITY MANAGER ACTIVITIES\nDisplay #0\n  mResumedActivity: changed-format"
            )

    def test_build_current_user_and_verbose_users_are_narrow_facts(self) -> None:
        build = parse_build_info("35\n15\nvendor/device/product:15/AP3A/test:user/release-keys\n")
        self.assertEqual(build.sdk_int, 35)
        self.assertEqual(build.release, "15")
        self.assertEqual(parse_current_user("10\n"), AndroidUserId(10))

        users = parse_users(_fixture("cmd_user_list_verbose.txt"))
        self.assertEqual([u.user_id for u in users.users], [AndroidUserId(0), AndroidUserId(10)])
        self.assertTrue(users.users[0].current)
        self.assertEqual(users.users[1].profile_group_id, AndroidUserId(0))
        self.assertIn("MANAGED_PROFILE", users.users[1].flags)

    def test_package_state_and_launcher_resolution_are_per_user_typed_facts(self) -> None:
        package = AndroidPackageName("com.example")
        state = parse_package_state(
            _fixture("dumpsys_package_example.txt"), AndroidUserId(10), package
        )
        self.assertTrue(state.installed)
        self.assertTrue(state.suspended)
        self.assertFalse(state.hidden)
        self.assertIs(state.enabled_state, AndroidPackageEnabledState.ENABLED)
        self.assertEqual(
            parse_launcher_component("com.example/.MainActivity\n", package).flattened,
            "com.example/.MainActivity",
        )
        self.assertIsNone(parse_launcher_component("No activity found\n", package))

    def test_window_and_inset_geometry_remains_native_facts(self) -> None:
        windows = parse_windows(_fixture("dumpsys_window_windows.txt"))
        self.assertEqual(len(windows.windows), 2)
        app = windows.windows[0]
        self.assertTrue(app.focused)
        self.assertTrue(app.has_surface)
        self.assertIs(app.view_visibility, AndroidWindowViewVisibility.VISIBLE)
        self.assertEqual(app.bounds, Rect(x=0, y=72, width=1080, height=2128))
        self.assertEqual(app.component.flattened, "com.example/.MainActivity")

        occlusions = parse_display_occlusions(
            _fixture("dumpsys_window_displays.txt"), AndroidDisplayId(0)
        )
        assert occlusions is not None
        self.assertEqual(
            [item.kind for item in occlusions.occlusions],
            [
                AndroidDisplayOcclusionKind.STATUS_BAR,
                AndroidDisplayOcclusionKind.NAVIGATION_BAR,
                AndroidDisplayOcclusionKind.IME,
                AndroidDisplayOcclusionKind.DISPLAY_CUTOUT,
            ],
        )
        self.assertFalse(occlusions.occlusions[2].visible)
        self.assertIsNone(
            parse_display_occlusions(
                _fixture("dumpsys_window_displays.txt"), AndroidDisplayId(99)
            )
        )


class ExtendedAndroidInspectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.endpoint = AdbServerEndpoint()
        self.selector = AdbTransportBySerial(AdbDeviceSerial("device-1"))

    def _run(self, cls, stdout: str, *args):
        fake = _FakeClient(stdout)
        inspector = cls(_client_factory=lambda endpoint: fake)
        result = inspector.inspect(self.endpoint, self.selector, *args)
        return result, fake

    def test_new_inspectors_use_specific_native_commands(self) -> None:
        build, build_fake = self._run(
            SmartSocketAdbBuildInfoInspector,
            "35\n15\nvendor/device/product:15/AP3A/test:user/release-keys\n",
        )
        self.assertEqual(build.sdk_int, 35)
        self.assertEqual(
            build_fake.calls[0][1],
            "getprop ro.build.version.sdk; getprop ro.build.version.release; getprop ro.build.fingerprint",
        )

        current, current_fake = self._run(SmartSocketAdbCurrentUserInspector, "10\n")
        self.assertEqual(current, AndroidUserId(10))
        self.assertEqual(current_fake.calls[0][1], "am get-current-user")

        users, users_fake = self._run(
            SmartSocketAdbUsersInspector, _fixture("cmd_user_list_verbose.txt")
        )
        self.assertEqual(len(users.users), 2)
        self.assertEqual(users_fake.calls[0][1], "cmd user list -v")

        launcher, launcher_fake = self._run(
            SmartSocketAdbLauncherActivityInspector,
            "com.example/.MainActivity\n",
            AndroidUserId(10),
            AndroidPackageName("com.example"),
        )
        self.assertIsNotNone(launcher)
        self.assertIn("resolve-activity --brief --user 10", launcher_fake.calls[0][1])

        windows, windows_fake = self._run(
            SmartSocketAdbWindowsInspector, _fixture("dumpsys_window_windows.txt")
        )
        self.assertEqual(len(windows.windows), 2)
        self.assertEqual(windows_fake.calls[0][1], "dumpsys window windows")

        insets, insets_fake = self._run(
            SmartSocketAdbDisplayOcclusionsInspector,
            _fixture("dumpsys_window_displays.txt"),
            AndroidDisplayId(0),
        )
        self.assertIsNotNone(insets)
        self.assertEqual(insets_fake.calls[0][1], "dumpsys window displays")


if __name__ == "__main__":
    unittest.main()
