from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from math import isfinite
from numbers import Real
from threading import Lock, Timer
from typing import Any
from uuid import uuid4

from eventing import EventPublisher
from scheduling.models import MisfirePolicy, ScheduleToken
from scheduling.ports import CalendarSchedule


_TimerFactory = Callable[[float, Callable[[], None]], Any]
_WallClock = Callable[[], datetime]


def _default_timer_factory(delay: float, callback: Callable[[], None]) -> Timer:
    timer = Timer(delay, callback)
    timer.daemon = True
    return timer


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _require_aware_datetime(value: datetime, *, field_name: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{field_name} must be datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value


def _normalize_positive_delay(value: timedelta) -> float:
    if not isinstance(value, timedelta):
        raise TypeError("delay must be timedelta")
    seconds = value.total_seconds()
    if not isfinite(seconds) or seconds <= 0.0:
        raise ValueError("delay must be finite and greater than zero")
    return seconds


class ThreadingTemporalScheduler:
    """In-process timer scheduler that delivers data events through an EventPublisher.

    Timers only publish their configured event. They never execute domain control
    effects directly, preserving the scheduling boundary defined by ``TemporalScheduler``.
    """

    def __init__(
        self,
        publisher: EventPublisher,
        *,
        _timer_factory: _TimerFactory = _default_timer_factory,
        _wall_clock: _WallClock = _utc_now,
    ) -> None:
        if not isinstance(publisher, EventPublisher):
            raise TypeError("publisher must satisfy EventPublisher")
        self._publisher = publisher
        self._timer_factory = _timer_factory
        self._wall_clock = _wall_clock
        self._lock = Lock()
        self._timers: dict[ScheduleToken, Any] = {}
        self._closed = False

    def schedule_at(
        self,
        deadline: datetime,
        event: object,
        *,
        misfire_policy: MisfirePolicy = MisfirePolicy.FIRE_ONCE,
    ) -> ScheduleToken:
        deadline = _require_aware_datetime(deadline, field_name="deadline")
        if not isinstance(misfire_policy, MisfirePolicy):
            raise TypeError("misfire_policy must be MisfirePolicy")
        now = _require_aware_datetime(self._wall_clock(), field_name="wall clock value")
        delay_seconds = (deadline - now).total_seconds()
        if delay_seconds <= 0.0:
            if misfire_policy is MisfirePolicy.SKIP:
                return ScheduleToken(uuid4().hex)
            delay_seconds = 0.0
        return self._register_timer(delay_seconds, event)

    def schedule_after(self, delay: timedelta, event: object) -> ScheduleToken:
        return self._register_timer(_normalize_positive_delay(delay), event)

    def schedule_recurring(
        self,
        schedule: CalendarSchedule,
        event: object,
        *,
        misfire_policy: MisfirePolicy = MisfirePolicy.FIRE_ONCE,
    ) -> ScheduleToken:
        if not isinstance(schedule, CalendarSchedule):
            raise TypeError("schedule must satisfy CalendarSchedule")
        if not isinstance(misfire_policy, MisfirePolicy):
            raise TypeError("misfire_policy must be MisfirePolicy")

        token = ScheduleToken(uuid4().hex)
        with self._lock:
            if self._closed:
                raise RuntimeError("scheduler is closed")
            self._timers[token] = None

        self._schedule_next_recurring(token, schedule, event, misfire_policy)
        return token

    def cancel(self, token: ScheduleToken) -> bool:
        if not isinstance(token, ScheduleToken):
            raise TypeError("token must be ScheduleToken")
        with self._lock:
            timer = self._timers.pop(token, None)
        if timer is None:
            return False
        timer.cancel()
        return True

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            timers = tuple(timer for timer in self._timers.values() if timer is not None)
            self._timers.clear()
        for timer in timers:
            timer.cancel()

    def _register_timer(self, delay_seconds: float, event: object) -> ScheduleToken:
        if isinstance(delay_seconds, bool) or not isinstance(delay_seconds, Real):
            raise TypeError("timer delay must be a real number")
        delay = float(delay_seconds)
        if not isfinite(delay) or delay < 0.0:
            raise ValueError("timer delay must be finite and non-negative")

        token = ScheduleToken(uuid4().hex)

        def deliver() -> None:
            with self._lock:
                if self._timers.pop(token, None) is None:
                    return
            self._publisher.publish(event)

        timer = self._timer_factory(delay, deliver)
        with self._lock:
            if self._closed:
                raise RuntimeError("scheduler is closed")
            self._timers[token] = timer
        timer.start()
        return token

    def _schedule_next_recurring(
        self,
        token: ScheduleToken,
        schedule: CalendarSchedule,
        event: object,
        misfire_policy: MisfirePolicy,
        *,
        after: datetime | None = None,
    ) -> None:
        now = _require_aware_datetime(self._wall_clock(), field_name="wall clock value")
        cursor = now if after is None else after
        next_deadline = schedule.next_after(cursor)
        if next_deadline is None:
            with self._lock:
                self._timers.pop(token, None)
            return
        next_deadline = _require_aware_datetime(
            next_deadline,
            field_name="calendar occurrence",
        )
        delay = max(0.0, (next_deadline - now).total_seconds())

        def deliver_recurring() -> None:
            with self._lock:
                if token not in self._timers or self._closed:
                    return
            current_now = _require_aware_datetime(
                self._wall_clock(),
                field_name="wall clock value",
            )
            if next_deadline <= current_now or misfire_policy is not MisfirePolicy.SKIP:
                self._publisher.publish(event)
            self._schedule_next_recurring(
                token,
                schedule,
                event,
                misfire_policy,
                after=max(next_deadline, current_now)
                if misfire_policy is MisfirePolicy.SKIP
                else next_deadline,
            )

        timer = self._timer_factory(delay, deliver_recurring)
        with self._lock:
            if token not in self._timers or self._closed:
                return
            self._timers[token] = timer
        timer.start()


__all__ = ["ThreadingTemporalScheduler"]
