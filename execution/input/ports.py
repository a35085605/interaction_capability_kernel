from __future__ import annotations

from typing import Protocol, TypeVar

from execution.input.domain import (
    KeyChord,
    KeyDown,
    KeyPress,
    KeyUp,
    PointerClick,
    PointerDrag,
    PointerMove,
    PointerScroll,
    TextEntry,
)
from native_attempt import NativeAttemptResult


PointT = TypeVar("PointT", contravariant=True)


class PointerMover(Protocol[PointT]):
    def move(self, operation: PointerMove[PointT]) -> NativeAttemptResult:
        ...


class PointerClicker(Protocol[PointT]):
    def click(self, operation: PointerClick[PointT]) -> NativeAttemptResult:
        ...


class PointerScroller(Protocol[PointT]):
    def scroll(self, operation: PointerScroll[PointT]) -> NativeAttemptResult:
        ...


class PointerDragger(Protocol[PointT]):
    def drag(self, operation: PointerDrag[PointT]) -> NativeAttemptResult:
        ...


class KeyStateController(Protocol):
    def key_down(self, operation: KeyDown) -> NativeAttemptResult:
        ...

    def key_up(self, operation: KeyUp) -> NativeAttemptResult:
        ...


class KeyPresser(Protocol):
    def press(self, operation: KeyPress) -> NativeAttemptResult:
        ...


class KeyChordController(Protocol):
    def chord(self, operation: KeyChord) -> NativeAttemptResult:
        ...


class TextController(Protocol):
    def type_text(self, operation: TextEntry) -> NativeAttemptResult:
        ...


class BackNavigator(Protocol):
    def back(self) -> NativeAttemptResult:
        ...
