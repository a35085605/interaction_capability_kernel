from __future__ import annotations

from datetime import timedelta
import unittest

from adb._internal.client import ShellV2Result
from adb.errors import AdbTimeoutError
from adb.server import AdbServerEndpoint
from adb.transport import AdbDeviceSerial, AdbTransportBySerial
from android.adb.adapters.input import (
    AdbBackNavigator,
    AdbKeyChordController,
    AdbKeyPresser,
    AdbTextController,
    AdbTouchController,
)
from android.display import AndroidDisplayId
from android.spatial import AndroidDisplayPoint
from execution.input import Key, KeyChord, KeyPress, TextEntry
from execution.touch import TouchDragAndDrop, TouchLongPress, TouchSwipe, TouchTap
from native_attempt import NativeAttemptStatus, NativeCompletionScope


class _FakeClient:
    def __init__(self, *, exit_code: int = 0, error: Exception | None = None) -> None:
        self.exit_code = exit_code
        self.error = error
        self.commands: list[str] = []

    def shell_v2(self, selector, command: str) -> ShellV2Result:
        self.commands.append(command)
        if self.error is not None:
            raise self.error
        return ShellV2Result(
            stdout=b"",
            stderr=b"bad input" if self.exit_code else b"",
            exit_code=self.exit_code,
        )


class AndroidAdbInputTests(unittest.TestCase):
    def setUp(self) -> None:
        self.endpoint = AdbServerEndpoint()
        self.selector = AdbTransportBySerial(AdbDeviceSerial("device-1"))
        self.display_id = AndroidDisplayId(3)

    def _touch(self, fake: _FakeClient) -> AdbTouchController:
        return AdbTouchController(
            self.endpoint,
            self.selector,
            self.display_id,
            _client_factory=lambda endpoint: fake,
        )

    def test_tap_targets_logical_display(self) -> None:
        fake = _FakeClient()
        result = self._touch(fake).tap(TouchTap(AndroidDisplayPoint(10, 20)))

        self.assertEqual(fake.commands, ["input -d 3 tap 10 20"])
        self.assertIs(result.status, NativeAttemptStatus.SUCCEEDED)
        self.assertIs(result.completion_scope, NativeCompletionScope.PROCESS_EXIT)
        self.assertEqual(result.native_code, "0")

    def test_long_press_swipe_and_drag_use_explicit_duration(self) -> None:
        fake = _FakeClient()
        controller = self._touch(fake)

        controller.long_press(
            TouchLongPress(AndroidDisplayPoint(5, 6), timedelta(milliseconds=750))
        )
        controller.swipe(
            TouchSwipe(
                AndroidDisplayPoint(1, 2),
                AndroidDisplayPoint(30, 40),
                timedelta(milliseconds=250),
            )
        )
        controller.drag_and_drop(
            TouchDragAndDrop(
                AndroidDisplayPoint(7, 8),
                AndroidDisplayPoint(70, 80),
                timedelta(milliseconds=600),
            )
        )

        self.assertEqual(
            fake.commands,
            [
                "input -d 3 swipe 5 6 5 6 750",
                "input -d 3 swipe 1 2 30 40 250",
                "input -d 3 draganddrop 7 8 70 80 600",
            ],
        )

    def test_key_back_and_chord_are_typed_fixed_commands(self) -> None:
        fake = _FakeClient()
        key = AdbKeyPresser(
            self.endpoint,
            self.selector,
            self.display_id,
            _client_factory=lambda endpoint: fake,
        )
        chord = AdbKeyChordController(
            self.endpoint,
            self.selector,
            self.display_id,
            _client_factory=lambda endpoint: fake,
        )
        back = AdbBackNavigator(
            self.endpoint,
            self.selector,
            self.display_id,
            _client_factory=lambda endpoint: fake,
        )

        key.press(KeyPress(Key("ENTER")))
        chord.chord(KeyChord((Key("CTRL_LEFT"), Key("A"))))
        back.back()

        self.assertEqual(
            fake.commands,
            [
                "input -d 3 keyevent KEYCODE_ENTER",
                "input -d 3 keycombination KEYCODE_CTRL_LEFT KEYCODE_A",
                "input -d 3 keyevent KEYCODE_BACK",
            ],
        )

    def test_timeout_is_not_collapsed_into_failed(self) -> None:
        fake = _FakeClient(error=AdbTimeoutError("read timed out"))

        result = self._touch(fake).tap(TouchTap(AndroidDisplayPoint(10, 20)))

        self.assertIs(result.status, NativeAttemptStatus.TIMED_OUT)
        self.assertIsNone(result.completion_scope)
        self.assertEqual(result.native_code, "AdbTimeoutError")

    def test_key_repeat_is_not_collapsed_into_one_native_attempt(self) -> None:
        fake = _FakeClient()
        key = AdbKeyPresser(
            self.endpoint,
            self.selector,
            self.display_id,
            _client_factory=lambda endpoint: fake,
        )

        result = key.press(KeyPress(Key("ENTER"), repeat=2))

        self.assertIs(result.status, NativeAttemptStatus.FAILED)
        self.assertIsNone(result.completion_scope)
        self.assertEqual(result.native_code, "unsupported_semantics")
        self.assertEqual(fake.commands, [])

    def test_key_token_does_not_expose_arbitrary_shell_text(self) -> None:
        fake = _FakeClient()
        key = AdbKeyPresser(
            self.endpoint,
            self.selector,
            self.display_id,
            _client_factory=lambda endpoint: fake,
        )

        with self.assertRaisesRegex(ValueError, "unsupported characters"):
            key.press(KeyPress(Key("ENTER;rm")))

        self.assertEqual(fake.commands, [])

    def test_text_adapter_is_deliberately_limited_to_portable_ascii(self) -> None:
        fake = _FakeClient()
        text = AdbTextController(
            self.endpoint,
            self.selector,
            self.display_id,
            _client_factory=lambda endpoint: fake,
        )

        result = text.type_text(TextEntry("hello world-1"))
        unsupported = text.type_text(TextEntry("你好"))

        self.assertIs(result.status, NativeAttemptStatus.SUCCEEDED)
        self.assertEqual(fake.commands, ["input -d 3 text hello%sworld-1"])
        self.assertIs(unsupported.status, NativeAttemptStatus.FAILED)
        self.assertEqual(unsupported.native_code, "unsupported_text_semantics")


if __name__ == "__main__":
    unittest.main()
