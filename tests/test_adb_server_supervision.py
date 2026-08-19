from __future__ import annotations

from datetime import datetime, timezone
import time
import unittest

from adb.errors import AdbServerConnectionError
from adb.server import AdbServerEndpoint, AdbServerStatus
from adb.server.lifecycle import (
    AdbServerEnsureOrchestrator,
    AdbServerEnsurePolicy,
    AdbServerEnsureStatus,
)
from adb.supervision import (
    AdbServerRecoveryExhausted,
    AdbServerRecoveryRetryDue,
    AdbServerSupervisionPolicy,
    AdbServerSupervisor,
)
from eventing.adapters import InMemoryEventBus
from native_attempt import NativeAttemptResult, NativeAttemptStatus, NativeCompletionScope
from scheduling import MisfirePolicy, ScheduleToken


class _StatusReader:
    def __init__(self, outcomes: list[object], *, repeat_last: bool = False) -> None:
        self.outcomes = outcomes
        self.repeat_last = repeat_last
        self.calls = 0

    def read(self, endpoint: AdbServerEndpoint) -> AdbServerStatus:
        self.calls += 1
        if self.repeat_last and len(self.outcomes) == 1:
            outcome = self.outcomes[0]
        else:
            outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        assert isinstance(outcome, AdbServerStatus)
        return outcome


class _ServerCommands:
    def __init__(self, attempt: NativeAttemptResult) -> None:
        self.attempt = attempt
        self.started = []
        self.stopped = []

    def start(self, operation):
        self.started.append(operation)
        return self.attempt

    def stop(self, operation):
        self.stopped.append(operation)
        return self.attempt


class _Clock:
    def __init__(self) -> None:
        self.value = 0.0

    def monotonic(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += seconds


class _Scheduler:
    def __init__(self) -> None:
        self.scheduled: list[tuple[object, object, ScheduleToken]] = []
        self.cancelled: list[ScheduleToken] = []
        self.counter = 0

    def schedule_at(self, deadline, event, *, misfire_policy=MisfirePolicy.FIRE_ONCE):
        return self._record(deadline, event)

    def schedule_after(self, delay, event):
        return self._record(delay, event)

    def schedule_recurring(self, schedule, event, *, misfire_policy=MisfirePolicy.FIRE_ONCE):
        return self._record(schedule, event)

    def cancel(self, token: ScheduleToken) -> bool:
        self.cancelled.append(token)
        return True

    def _record(self, timing, event) -> ScheduleToken:
        self.counter += 1
        token = ScheduleToken(f"schedule-{self.counter}")
        self.scheduled.append((timing, event, token))
        return token


def _endpoint() -> AdbServerEndpoint:
    return AdbServerEndpoint("127.0.0.1", 5037)


def _attempt() -> NativeAttemptResult:
    now = datetime(2026, 8, 19, tzinfo=timezone.utc)
    return NativeAttemptResult(
        status=NativeAttemptStatus.SUCCEEDED,
        completion_scope=NativeCompletionScope.PROCESS_EXIT,
        backend_id="test-adb",
        started_at=now,
        finished_at=now,
        native_code="0",
    )


def _wait_until(predicate, *, timeout_seconds: float = 1.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while not predicate():
        if time.monotonic() >= deadline:
            raise AssertionError("timed out waiting for asynchronous server supervision work")
        time.sleep(0.005)


class AdbServerSupervisorTests(unittest.TestCase):
    def _supervisor(self, reader: _StatusReader, *, max_attempts: int | None = None):
        bus = InMemoryEventBus()
        commands = _ServerCommands(_attempt())
        scheduler = _Scheduler()
        clock = _Clock()
        ensure = AdbServerEnsureOrchestrator(
            _endpoint(),
            reader,
            commands,
            commands,
            bus,
            _monotonic=clock.monotonic,
            _sleep=clock.sleep,
        )
        policy = AdbServerSupervisionPolicy(
            ensure_policy=AdbServerEnsurePolicy(0.2, 0.1),
            retry_initial_seconds=1,
            retry_max_seconds=8,
            retry_multiplier=2,
            retry_jitter_ratio=0,
            max_attempts=max_attempts,
        )
        supervisor = AdbServerSupervisor(
            _endpoint(),
            bus,
            ensure,
            scheduler,
            policy,
            _random=lambda: 0.5,
        )
        return bus, commands, scheduler, supervisor

    def test_start_requires_explicit_recovery_policy(self) -> None:
        reader = _StatusReader([AdbServerStatus()])
        _, _, _, supervisor = self._supervisor(reader)
        with self.assertRaises(TypeError):
            supervisor.start()  # type: ignore[call-arg]

    def test_start_establishes_running_condition(self) -> None:
        reader = _StatusReader([
            AdbServerConnectionError("down"),
            AdbServerStatus(),
        ])
        _, commands, scheduler, supervisor = self._supervisor(reader)
        result = supervisor.start(recovery_enabled=True)
        self.assertIs(result.status, AdbServerEnsureStatus.SATISFIED)
        self.assertTrue(supervisor.desired_running)
        self.assertTrue(supervisor.recovery_enabled)
        self.assertTrue(supervisor.recovery_armed)
        self.assertEqual(len(commands.started), 1)
        self.assertEqual(scheduler.scheduled, [])

    def test_disable_recovery_cancels_retry_without_stopping_server(self) -> None:
        reader = _StatusReader([AdbServerConnectionError("down")], repeat_last=True)
        _, commands, scheduler, supervisor = self._supervisor(reader)
        result = supervisor.start(recovery_enabled=True)
        self.assertIs(result.status, AdbServerEnsureStatus.TIMED_OUT)
        self.assertEqual(len(scheduler.scheduled), 1)
        _, retry_event, token = scheduler.scheduled[0]
        self.assertIsInstance(retry_event, AdbServerRecoveryRetryDue)
        epoch = supervisor.recovery_epoch
        supervisor.set_recovery_enabled(False)
        self.assertGreater(supervisor.recovery_epoch, epoch)
        self.assertIn(token, scheduler.cancelled)
        self.assertTrue(supervisor.desired_running)
        self.assertFalse(supervisor.recovery_enabled)
        self.assertFalse(supervisor.recovery_armed)
        self.assertEqual(commands.stopped, [])

    def test_reenable_recovery_reconciles_immediately(self) -> None:
        reader = _StatusReader([AdbServerConnectionError("down")], repeat_last=True)
        _, _, scheduler, supervisor = self._supervisor(reader)
        supervisor.start(recovery_enabled=False)
        self.assertEqual(scheduler.scheduled, [])
        calls_before_enable = reader.calls
        supervisor.set_recovery_enabled(True)
        _wait_until(lambda: reader.calls > calls_before_enable)
        self.assertTrue(supervisor.recovery_enabled)
        self.assertTrue(supervisor.recovery_armed)
        self.assertEqual(len(scheduler.scheduled), 1)

    def test_enable_recovery_without_running_intent_is_rejected(self) -> None:
        reader = _StatusReader([AdbServerStatus()])
        _, _, _, supervisor = self._supervisor(reader)
        with self.assertRaises(RuntimeError):
            supervisor.set_recovery_enabled(True)
        self.assertFalse(supervisor.desired_running)
        self.assertFalse(supervisor.recovery_enabled)
        self.assertFalse(supervisor.recovery_armed)

    def test_recovery_cycle_exhaustion_is_server_owned(self) -> None:
        reader = _StatusReader([AdbServerConnectionError("down")], repeat_last=True)
        bus, _, scheduler, supervisor = self._supervisor(reader, max_attempts=2)
        exhausted: list[AdbServerRecoveryExhausted] = []
        bus.subscribe(AdbServerRecoveryExhausted, exhausted.append)
        supervisor.start(recovery_enabled=True)
        _, retry_event, _ = scheduler.scheduled[0]
        bus.publish(retry_event)
        _wait_until(lambda: len(exhausted) == 1)
        self.assertEqual(exhausted[0].attempts, 2)
        self.assertEqual(exhausted[0].cycle_id, retry_event.cycle_id)
        self.assertEqual(exhausted[0].endpoint, _endpoint())

    def test_stop_invalidates_running_recovery_and_establishes_unavailable(self) -> None:
        reader = _StatusReader([
            AdbServerStatus(),
            AdbServerStatus(),
            AdbServerConnectionError("stopped"),
        ])
        _, commands, _, supervisor = self._supervisor(reader)
        supervisor.start(recovery_enabled=True)
        epoch = supervisor.recovery_epoch
        result = supervisor.stop()
        self.assertIs(result.status, AdbServerEnsureStatus.SATISFIED)
        self.assertFalse(supervisor.desired_running)
        self.assertFalse(supervisor.recovery_enabled)
        self.assertFalse(supervisor.recovery_armed)
        self.assertGreater(supervisor.recovery_epoch, epoch)
        self.assertEqual(len(commands.stopped), 1)

    def test_close_does_not_stop_native_server(self) -> None:
        reader = _StatusReader([AdbServerStatus()])
        _, commands, _, supervisor = self._supervisor(reader)
        supervisor.start(recovery_enabled=True)
        supervisor.close()
        self.assertFalse(supervisor.recovery_enabled)
        self.assertFalse(supervisor.recovery_armed)
        self.assertEqual(commands.stopped, [])


if __name__ == "__main__":
    unittest.main()
