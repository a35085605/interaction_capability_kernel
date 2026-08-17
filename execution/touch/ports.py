from __future__ import annotations

from typing import Protocol, TypeVar

from execution.touch.domain import TouchDragAndDrop, TouchLongPress, TouchSwipe, TouchTap
from native_attempt import NativeAttemptResult


PointT = TypeVar("PointT", contravariant=True)


class TouchController(Protocol[PointT]):
    def tap(self, operation: TouchTap[PointT]) -> NativeAttemptResult:
        ...

    def long_press(self, operation: TouchLongPress[PointT]) -> NativeAttemptResult:
        ...

    def swipe(self, operation: TouchSwipe[PointT]) -> NativeAttemptResult:
        ...

    def drag_and_drop(
        self, operation: TouchDragAndDrop[PointT]
    ) -> NativeAttemptResult:
        ...


__all__ = ["TouchController"]
