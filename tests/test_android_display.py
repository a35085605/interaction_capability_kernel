from __future__ import annotations

import subprocess
import sys
import unittest

from android.display import (
    AndroidDisplayId,
    AndroidDisplayRotation,
    AndroidDisplayState,
    AndroidDisplaysSnapshot,
)
from android.spatial import AndroidDisplayPoint, AndroidDisplaySurface
from geometry import Rect, Size


class AndroidDisplayStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.display_id = AndroidDisplayId(0)
        self.bounds = Rect(x=0, y=0, width=1080, height=2400)

    def test_display_id_is_android_runtime_integer_identity(self) -> None:
        self.assertEqual(int(self.display_id), 0)
        self.assertEqual(str(self.display_id), "0")
        with self.assertRaises(TypeError):
            AndroidDisplayId("0")  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            AndroidDisplayId(-1)

    def test_surface_rotation_codes_are_normalized_to_degrees(self) -> None:
        self.assertIs(
            AndroidDisplayRotation.from_surface_rotation(0),
            AndroidDisplayRotation.ROTATION_0,
        )
        self.assertIs(
            AndroidDisplayRotation.from_surface_rotation(1),
            AndroidDisplayRotation.ROTATION_90,
        )
        self.assertIs(
            AndroidDisplayRotation.from_surface_rotation(2),
            AndroidDisplayRotation.ROTATION_180,
        )
        self.assertIs(
            AndroidDisplayRotation.from_surface_rotation(3),
            AndroidDisplayRotation.ROTATION_270,
        )
        with self.assertRaises(ValueError):
            AndroidDisplayRotation.from_surface_rotation(90)

    def test_display_remains_an_independent_android_fact(self) -> None:
        state = AndroidDisplayState(
            display_id=self.display_id,
            bounds=self.bounds,
            rotation=AndroidDisplayRotation.ROTATION_0,
            density_dpi=420,
            physical_size=Size(width=1080, height=2400),
        )

        self.assertEqual(
            state.surface,
            AndroidDisplaySurface(self.display_id, self.bounds),
        )
        self.assertEqual(state.density_dpi, 420)

    def test_displays_snapshot_is_a_complete_typed_listing(self) -> None:
        display = AndroidDisplayState(
            display_id=self.display_id,
            bounds=self.bounds,
            rotation=AndroidDisplayRotation.ROTATION_0,
        )
        snapshot = AndroidDisplaysSnapshot((display,))

        self.assertEqual(snapshot.displays, (display,))
        with self.assertRaisesRegex(TypeError, "displays must be a tuple"):
            AndroidDisplaysSnapshot([display])  # type: ignore[arg-type]

    def test_android_display_point_has_display_specific_type(self) -> None:
        point = AndroidDisplayPoint(x=12, y=34)
        self.assertEqual((point.x, point.y), (12, 34))


class AndroidDisplayOwnershipBoundaryTests(unittest.TestCase):
    def test_android_display_models_do_not_load_adb(self) -> None:
        script = """
import sys
import android.display
import android.spatial

assert 'adb' not in sys.modules
assert 'geometry' in sys.modules
"""
        subprocess.run([sys.executable, "-c", script], check=True)


if __name__ == "__main__":
    unittest.main()
