from __future__ import annotations

from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    """Injectable, read-only source for wall-clock and monotonic time.

    Wall-clock time supports dates and deadlines, while monotonic time supports
    elapsed duration and freshness. A Clock reports time only; it does not own
    scheduling, timeout, or retry policy.
    """

    def now(self) -> datetime:
        """Return the current timezone-aware wall-clock time."""
        ...

    def monotonic(self) -> float:
        """Return a non-decreasing process-local time value in seconds."""
        ...


__all__ = ["Clock"]
