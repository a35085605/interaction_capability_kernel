from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, tzinfo
import time


@dataclass(frozen=True, slots=True)
class SystemClock:
    """Production clock backed by the host wall and monotonic clocks."""

    timezone: tzinfo = timezone.utc

    def __post_init__(self) -> None:
        if not isinstance(self.timezone, tzinfo):
            raise TypeError("timezone must be tzinfo")

    def now(self) -> datetime:
        return datetime.now(self.timezone)

    def monotonic(self) -> float:
        return time.monotonic()
