from __future__ import annotations

from pathlib import Path
import unittest

from adb._internal.client import ShellV2Result
from adb.errors import AdbProtocolError
from adb.server import AdbServerEndpoint
from adb.transport import AdbDeviceSerial, AdbTransportBySerial
from android.adb.adapters.query import (
    SmartSocketAdbBootStateInspector,
    SmartSocketAdbDisplayInspector,
    SmartSocketAdbDisplaysInspector,
    SmartSocketAdbKeyguardStateInspector,
    SmartSocketAdbPackageStateInspector,
    SmartSocketAdbPhysicalDisplaysInspector,
    SmartSocketAdbPowerStateInspector,
    SmartSocketAdbResumedActivitiesInspector,
    SmartSocketAdbUserStateInspector,
    parse_android_user_state,
    parse_dumpsys_display,
    parse_keyguard_state,
    parse_power_state,
    parse_resumed_activities,
    parse_surfaceflinger_display_ids,
)
from android.display import AndroidDisplayId, AndroidDisplayRotation, AndroidPhysicalDisplayId
from android.identity import AndroidPackageName, AndroidUserId
from android.runtime import AndroidBootState, AndroidPowerWakefulness, AndroidUserPhase
from geometry import Rect


_FIXTURES = Path(__file__).parent / "fixtures" / "android"


def _fixture(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


class _FakeClient:
    def __init__(self, result: ShellV2Result) -> None:
        self.result = result
        self.calls: list[tuple[object, str]] = []

    def shell_v2(self, selector, command: str) -> ShellV2Result:
        self.calls.append((selector, command))
        return self.result


class AndroidAdbDisplayParserTests(unittest.TestCase):
    def test_parses_recent_golden_fixture_and_keeps_physical_relation_explicit(self) -> None:
        snapshot = parse_dumpsys_display(_fixture("dumpsys_display_recent.txt"))

        self.assertEqual([int(item.display_id) for item in snapshot.displays], [0, 7])
        first, second = snapshot.displays
        self.assertEqual(first.bounds, Rect(x=0, y=0, width=1080, height=2400))
        self.assertIs(first.rotation, AndroidDisplayRotation.ROTATION_90)
        self.assertEqual(first.density_dpi, 420)
        self.assertEqual(
            first.physical_display_id,
            AndroidPhysicalDisplayId(4619827259835644672),
        )
        self.assertIsNone(second.physical_display_id)

    def test_android10_display_fixture_uses_override_display_info(self) -> None:
        snapshot = parse_dumpsys_display(_fixture("dumpsys_display_android10.txt"))

        self.assertEqual(len(snapshot.displays), 1)
        display = snapshot.displays[0]
        self.assertEqual(display.display_id, AndroidDisplayId(7))
        self.assertEqual(display.bounds, Rect(x=0, y=0, width=1024, height=768))
        self.assertIs(display.rotation, AndroidDisplayRotation.ROTATION_180)
        self.assertEqual(display.density_dpi, 320)

    def test_parser_fails_closed_when_display_format_is_unknown(self) -> None:
        with self.assertRaisesRegex(AdbProtocolError, "unsupported dumpsys display format"):
            parse_dumpsys_display("DisplayManagerService state changed format completely")

        with self.assertRaisesRegex(AdbProtocolError, "supported Android display format"):
            parse_dumpsys_display('mBaseDisplayInfo=DisplayInfo{"Built-in", displayId 0}')

    def test_unsupported_rotation_is_protocol_failure(self) -> None:
        with self.assertRaisesRegex(AdbProtocolError, "unsupported rotation"):
            parse_dumpsys_display(
                'mBaseDisplayInfo=DisplayInfo{"Bad", displayId 0, real 10 x 20, rotation 9, density 100 dpi}'
            )

    def test_surfaceflinger_physical_display_fixture(self) -> None:
        snapshot = parse_surfaceflinger_display_ids(
            _fixture("surfaceflinger_display_ids.txt")
        )

        self.assertEqual(
            [int(item.display_id) for item in snapshot.displays],
            [21691504607621632, 9834494747159041],
        )
        self.assertEqual(snapshot.displays[0].hwc_display_id, 0)
        self.assertEqual(snapshot.displays[0].port, 0)
        self.assertEqual(snapshot.displays[0].pnp_id, "SHP")
        self.assertEqual(snapshot.displays[0].display_name, "LQ123P1JX32")


class AndroidAdbFactParserTests(unittest.TestCase):
    def test_user_state_is_per_user_and_not_started_is_absence(self) -> None:
        user = AndroidUserId(10)
        state = parse_android_user_state(
            "[UserState: id=10, state=RUNNING_UNLOCKED, lastState=RUNNING_UNLOCKING, switching=false]\n",
            user,
        )
        self.assertIsNotNone(state)
        assert state is not None
        self.assertIs(state.phase, AndroidUserPhase.RUNNING_UNLOCKED)
        self.assertIsNone(parse_android_user_state("User is not started: 10\n", user))

    def test_resumed_activity_fixture_is_scoped_by_display_user_and_task(self) -> None:
        snapshot = parse_resumed_activities(_fixture("dumpsys_activity_activities.txt"))

        self.assertEqual(len(snapshot.activities), 2)
        first, second = snapshot.activities
        self.assertEqual(first.user_id, AndroidUserId(0))
        self.assertEqual(first.display_id, AndroidDisplayId(0))
        self.assertEqual(first.component.flattened, "com.example/.MainActivity")
        self.assertEqual(first.task_id, 42)
        self.assertEqual(second.user_id, AndroidUserId(10))
        self.assertEqual(second.display_id, AndroidDisplayId(7))
        self.assertEqual(second.task_id, 99)

    def test_power_and_keyguard_are_independent_facts(self) -> None:
        power = parse_power_state(_fixture("dumpsys_power.txt"))
        keyguard = parse_keyguard_state(_fixture("dumpsys_window_policy.txt"))

        self.assertIs(power.wakefulness, AndroidPowerWakefulness.AWAKE)
        self.assertTrue(keyguard.showing)


class AndroidAdbInspectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.endpoint = AdbServerEndpoint()
        self.selector = AdbTransportBySerial(AdbDeviceSerial("device-1"))

    def _inspector(self, cls, stdout: str):
        fake = _FakeClient(
            ShellV2Result(stdout=stdout.encode(), stderr=b"", exit_code=0)
        )
        return cls(_client_factory=lambda endpoint: fake), fake

    def test_boot_inspector_queries_sys_boot_completed(self) -> None:
        inspector, fake = self._inspector(SmartSocketAdbBootStateInspector, "1\n")

        state = inspector.inspect(self.endpoint, self.selector)

        self.assertIs(state, AndroidBootState.BOOTED)
        self.assertEqual(fake.calls, [(self.selector, "getprop sys.boot_completed")])

    def test_displays_and_single_display_inspectors(self) -> None:
        inspector, fake = self._inspector(
            SmartSocketAdbDisplaysInspector,
            _fixture("dumpsys_display_recent.txt"),
        )
        snapshot = inspector.inspect(self.endpoint, self.selector)
        single = SmartSocketAdbDisplayInspector(inspector)

        self.assertEqual(len(snapshot.displays), 2)
        self.assertIsNotNone(single.inspect(self.endpoint, self.selector, AndroidDisplayId(0)))
        self.assertIsNone(single.inspect(self.endpoint, self.selector, AndroidDisplayId(9)))
        self.assertEqual(fake.calls[0], (self.selector, "dumpsys display"))

    def test_physical_display_inspector_uses_surfaceflinger_display_ids(self) -> None:
        inspector, fake = self._inspector(
            SmartSocketAdbPhysicalDisplaysInspector,
            _fixture("surfaceflinger_display_ids.txt"),
        )

        snapshot = inspector.inspect(self.endpoint, self.selector)

        self.assertEqual(len(snapshot.displays), 2)
        self.assertEqual(
            fake.calls,
            [(self.selector, "dumpsys SurfaceFlinger --display-id")],
        )

    def test_user_package_activity_power_and_keyguard_inspectors_use_typed_scopes(self) -> None:
        user = AndroidUserId(10)
        package = AndroidPackageName("com.example")

        user_inspector, user_fake = self._inspector(
            SmartSocketAdbUserStateInspector,
            "[UserState: id=10, state=RUNNING_UNLOCKED, lastState=RUNNING_UNLOCKING, switching=false]\n",
        )
        package_inspector, package_fake = self._inspector(
            SmartSocketAdbPackageStateInspector,
            _fixture("dumpsys_package_example.txt"),
        )
        activity_inspector, activity_fake = self._inspector(
            SmartSocketAdbResumedActivitiesInspector,
            _fixture("dumpsys_activity_activities.txt"),
        )
        power_inspector, power_fake = self._inspector(
            SmartSocketAdbPowerStateInspector,
            _fixture("dumpsys_power.txt"),
        )
        keyguard_inspector, keyguard_fake = self._inspector(
            SmartSocketAdbKeyguardStateInspector,
            _fixture("dumpsys_window_policy.txt"),
        )

        self.assertIsNotNone(user_inspector.inspect(self.endpoint, self.selector, user))
        self.assertTrue(
            package_inspector.inspect(self.endpoint, self.selector, user, package).installed
        )
        self.assertEqual(
            len(activity_inspector.inspect(self.endpoint, self.selector).activities), 2
        )
        self.assertIs(
            power_inspector.inspect(self.endpoint, self.selector).wakefulness,
            AndroidPowerWakefulness.AWAKE,
        )
        self.assertTrue(keyguard_inspector.inspect(self.endpoint, self.selector).showing)
        self.assertEqual(user_fake.calls, [(self.selector, "am get-started-user-state 10")])
        self.assertEqual(
            package_fake.calls,
            [(self.selector, "dumpsys package com.example")],
        )
        self.assertEqual(activity_fake.calls, [(self.selector, "dumpsys activity activities")])
        self.assertEqual(power_fake.calls, [(self.selector, "dumpsys power")])
        self.assertEqual(keyguard_fake.calls, [(self.selector, "dumpsys window policy")])


if __name__ == "__main__":
    unittest.main()
