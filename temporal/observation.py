from __future__ import annotations

from temporal.models import TemporalSnapshot
from temporal.ports import Clock


def observe_time(
    clock: Clock,
    *,
    observer_id: str = "temporal.clock",
) -> TemporalSnapshot:
    """Read wall-clock and monotonic time as one temporal observation."""

    if not hasattr(clock, "now") or not hasattr(clock, "monotonic"):
        raise TypeError("clock must provide now() and monotonic()")

    return TemporalSnapshot(
        observed_at=clock.now(),
        monotonic_seconds=clock.monotonic(),
        observer_id=observer_id,
    )
