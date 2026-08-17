from __future__ import annotations

from typing import Protocol

from native_attempt import NativeAttemptResult
from windows.command.domain import (
    WindowActivation,
    WindowBoundsChange,
    WindowMinimize,
    WindowMove,
    WindowResize,
    WindowRestore,
)


class WindowActivator(Protocol):
    def activate(self, operation: WindowActivation) -> NativeAttemptResult:
        ...


class WindowMinimizer(Protocol):
    def minimize(self, operation: WindowMinimize) -> NativeAttemptResult:
        ...


class WindowRestorer(Protocol):
    def restore(self, operation: WindowRestore) -> NativeAttemptResult:
        ...


class WindowMover(Protocol):
    def move(self, operation: WindowMove) -> NativeAttemptResult:
        ...


class WindowResizer(Protocol):
    def resize(self, operation: WindowResize) -> NativeAttemptResult:
        ...


class WindowBoundsController(Protocol):
    def set_bounds(
        self,
        operation: WindowBoundsChange,
    ) -> NativeAttemptResult:
        ...
