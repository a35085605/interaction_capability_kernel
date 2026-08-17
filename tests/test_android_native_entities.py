from __future__ import annotations

import unittest

from android.application import AndroidPackageState, AndroidResumedActivity
from android.display import AndroidDisplayId, AndroidPhysicalDisplayId
from android.identity import AndroidComponentName, AndroidPackageName, AndroidUserId
from android.runtime import AndroidPowerState, AndroidPowerWakefulness, AndroidUserPhase, AndroidUserState


class AndroidNativeEntityTests(unittest.TestCase):
    def test_user_package_and_component_are_typed_native_identities(self) -> None:
        user = AndroidUserId(10)
        package = AndroidPackageName("com.example.app")
        component = AndroidComponentName(package, ".MainActivity")

        self.assertEqual(int(user), 10)
        self.assertEqual(str(package), "com.example.app")
        self.assertEqual(component.flattened, "com.example.app/.MainActivity")

        with self.assertRaises(ValueError):
            AndroidUserId(-1)
        with self.assertRaises(ValueError):
            AndroidPackageName("com.example;rm")
        with self.assertRaises(ValueError):
            AndroidComponentName(package, ".Main Activity")

    def test_package_and_activity_facts_preserve_user_and_display_scope(self) -> None:
        user = AndroidUserId(10)
        package = AndroidPackageName("com.example")
        component = AndroidComponentName(package, ".Main")

        package_state = AndroidPackageState(user, package, installed=True)
        activity = AndroidResumedActivity(
            user_id=user,
            display_id=AndroidDisplayId(7),
            component=component,
            task_id=42,
        )

        self.assertTrue(package_state.installed)
        self.assertEqual(activity.user_id, user)
        self.assertEqual(activity.display_id, AndroidDisplayId(7))
        self.assertEqual(activity.task_id, 42)

    def test_readiness_facts_are_independent(self) -> None:
        user_state = AndroidUserState(AndroidUserId(0), AndroidUserPhase.RUNNING_UNLOCKED)
        power_state = AndroidPowerState(AndroidPowerWakefulness.AWAKE)

        self.assertIs(user_state.phase, AndroidUserPhase.RUNNING_UNLOCKED)
        self.assertIs(power_state.wakefulness, AndroidPowerWakefulness.AWAKE)

    def test_logical_and_physical_display_ids_are_not_interchangeable(self) -> None:
        logical = AndroidDisplayId(0)
        physical = AndroidPhysicalDisplayId(4619827259835644672)

        self.assertNotEqual(logical, physical)
        self.assertEqual(int(physical), 4619827259835644672)


if __name__ == "__main__":
    unittest.main()
