from __future__ import annotations

from datetime import timedelta
import unittest

from eventing.adapters import InMemoryEventBus
from scheduling.adapters import ThreadingTemporalScheduler


class _FakeTimer:
    def __init__(self, delay: float, callback) -> None:
        self.delay = delay
        self.callback = callback
        self.started = False
        self.cancelled = False

    def start(self) -> None:
        self.started = True

    def cancel(self) -> None:
        self.cancelled = True

    def fire(self) -> None:
        self.callback()


class _TimerFactory:
    def __init__(self) -> None:
        self.timers: list[_FakeTimer] = []

    def __call__(self, delay: float, callback) -> _FakeTimer:
        timer = _FakeTimer(delay, callback)
        self.timers.append(timer)
        return timer


class ThreadingTemporalSchedulerTests(unittest.TestCase):
    def test_schedule_after_delivers_event_through_bus(self) -> None:
        bus = InMemoryEventBus()
        observed: list[str] = []
        bus.subscribe(str, observed.append)
        timers = _TimerFactory()
        scheduler = ThreadingTemporalScheduler(bus, _timer_factory=timers)

        token = scheduler.schedule_after(timedelta(seconds=2), "retry-due")

        self.assertTrue(timers.timers[0].started)
        self.assertEqual(timers.timers[0].delay, 2.0)
        self.assertEqual(observed, [])
        timers.timers[0].fire()
        self.assertEqual(observed, ["retry-due"])
        self.assertFalse(scheduler.cancel(token))

    def test_cancel_prevents_scheduled_delivery(self) -> None:
        bus = InMemoryEventBus()
        observed: list[str] = []
        bus.subscribe(str, observed.append)
        timers = _TimerFactory()
        scheduler = ThreadingTemporalScheduler(bus, _timer_factory=timers)

        token = scheduler.schedule_after(timedelta(seconds=1), "retry-due")
        self.assertTrue(scheduler.cancel(token))
        self.assertTrue(timers.timers[0].cancelled)
        timers.timers[0].fire()

        self.assertEqual(observed, [])


if __name__ == "__main__":
    unittest.main()
