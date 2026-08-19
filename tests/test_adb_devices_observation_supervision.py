from __future__ import annotations

from datetime import datetime, timezone
import time
import unittest

from adb.errors import AdbServerConnectionError
from adb.server import AdbServerEndpoint, AdbServerStatus
from adb.server.lifecycle import (
    AdbServerEnsureAvailable,
    AdbServerEnsureOrchestrator,
    AdbServerEnsurePolicy,
    AdbServerEnsureStatus,
)
from adb.server.signal import AdbServerCommandCompleted, AdbServerEnsureCompleted, AdbServerProbeCompleted
from adb.supervision import (
    AdbDevicesObservationEstablishmentExhausted,
    AdbDevicesObservationEstablishmentRetryDue,
    AdbDevicesObservationSupervisionPolicy,
    AdbDevicesObservationSupervisor,
)
from adb.transport.observation.contracts import AdbObservationSessionId
from adb.transport.observation.establishment import (
    AdbDevicesObservationEstablishment,
    AdbDevicesObservationEstablishmentOrchestrator,
    AdbDevicesObservationEstablishmentPolicy,
    AdbDevicesObservationEstablishmentStatus,
)
from adb.transport.observation.signal import (
    AdbDevicesObservationFailed,
    AdbDevicesObservationFailure,
    AdbDevicesObservationStarted,
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


class _Observation:
    def __init__(self, endpoint: AdbServerEndpoint, bus: InMemoryEventBus, outcomes: list[str]) -> None:
        self.endpoint = endpoint
        self.bus = bus
        self.outcomes = outcomes
        self.generation = 0
        self.active_session_id = None
        self.closed = False
        self.stop_calls = 0

    def start(self) -> AdbObservationSessionId:
        self.generation += 1
        session_id = AdbObservationSessionId(self.endpoint, self.generation)
        self.active_session_id = session_id
        outcome = self.outcomes.pop(0)
        if outcome == "started":
            self.bus.publish(AdbDevicesObservationStarted(self.endpoint, session_id))
        elif outcome == "connection_failed":
            self.active_session_id = None
            self.bus.publish(
                AdbDevicesObservationFailed(
                    self.endpoint,
                    session_id,
                    AdbDevicesObservationFailure.SERVER_CONNECTION,
                    "connection failed",
                )
            )
        elif outcome == "protocol_failed":
            self.active_session_id = None
            self.bus.publish(
                AdbDevicesObservationFailed(
                    self.endpoint,
                    session_id,
                    AdbDevicesObservationFailure.PROTOCOL,
                    "protocol failed",
                )
            )
        else:
            raise AssertionError(f"unsupported observation outcome: {outcome}")
        return session_id

    def stop(self) -> None:
        self.stop_calls += 1
        self.active_session_id = None

    def close(self) -> None:
        self.closed = True
        self.active_session_id = None


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


def _attempt(status: NativeAttemptStatus = NativeAttemptStatus.SUCCEEDED) -> NativeAttemptResult:
    now = datetime(2026, 8, 17, tzinfo=timezone.utc)
    return NativeAttemptResult(
        status=status,
        completion_scope=(NativeCompletionScope.PROCESS_EXIT if status is NativeAttemptStatus.SUCCEEDED else None),
        backend_id="test-adb",
        started_at=now,
        finished_at=now,
        native_code="0" if status is NativeAttemptStatus.SUCCEEDED else "1",
    )


def _wait_until(predicate, *, timeout_seconds: float = 1.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while not predicate():
        if time.monotonic() >= deadline:
            raise AssertionError("timed out waiting for asynchronous observation supervision work")
        time.sleep(0.005)


class AdbServerEnsureOrchestratorTests(unittest.TestCase):
    def test_ensure_available_preserves_probe_command_and_verification_signals(self) -> None:
        bus = InMemoryEventBus()
        signals: list[object] = []
        bus.subscribe(object, signals.append)
        reader = _StatusReader([AdbServerConnectionError("refused"), AdbServerStatus(version="0010")])
        commands = _ServerCommands(_attempt())
        clock = _Clock()
        orchestrator = AdbServerEnsureOrchestrator(
            _endpoint(), reader, commands, commands, bus, _monotonic=clock.monotonic, _sleep=clock.sleep
        )
        result = orchestrator.ensure(AdbServerEnsureAvailable(_endpoint(), AdbServerEnsurePolicy(1, 0.1)))
        self.assertIs(result.status, AdbServerEnsureStatus.SATISFIED)
        self.assertEqual(len(commands.started), 1)
        self.assertEqual(
            [type(signal) for signal in signals],
            [AdbServerProbeCompleted, AdbServerCommandCompleted, AdbServerProbeCompleted, AdbServerEnsureCompleted],
        )

    def test_already_available_does_not_issue_native_command(self) -> None:
        bus = InMemoryEventBus()
        reader = _StatusReader([AdbServerStatus()])
        commands = _ServerCommands(_attempt())
        orchestrator = AdbServerEnsureOrchestrator(_endpoint(), reader, commands, commands, bus)
        result = orchestrator.ensure(AdbServerEnsureAvailable(_endpoint(), AdbServerEnsurePolicy(1, 0.1)))
        self.assertIs(result.status, AdbServerEnsureStatus.SATISFIED)
        self.assertEqual(result.attempts, ())
        self.assertEqual(commands.started, [])

    def test_unsatisfied_ensure_times_out_after_fresh_verification(self) -> None:
        bus = InMemoryEventBus()
        reader = _StatusReader([AdbServerConnectionError("down")], repeat_last=True)
        commands = _ServerCommands(_attempt())
        clock = _Clock()
        orchestrator = AdbServerEnsureOrchestrator(
            _endpoint(), reader, commands, commands, bus, _monotonic=clock.monotonic, _sleep=clock.sleep
        )
        result = orchestrator.ensure(AdbServerEnsureAvailable(_endpoint(), AdbServerEnsurePolicy(0.2, 0.1)))
        self.assertIs(result.status, AdbServerEnsureStatus.TIMED_OUT)
        self.assertGreaterEqual(reader.calls, 3)
        self.assertEqual(len(result.attempts), 1)


class AdbDevicesObservationEstablishmentTests(unittest.TestCase):
    def test_establishment_requires_started_evidence_without_server_mutation(self) -> None:
        bus = InMemoryEventBus()
        observation = _Observation(_endpoint(), bus, ["started"])
        establishment = AdbDevicesObservationEstablishmentOrchestrator(
            _endpoint(), bus, observation
        )
        result = establishment.establish(
            AdbDevicesObservationEstablishment(
                _endpoint(),
                AdbDevicesObservationEstablishmentPolicy(2.0),
            )
        )
        self.assertIs(result.status, AdbDevicesObservationEstablishmentStatus.SATISFIED)
        self.assertEqual(result.observation_session_id.generation, 1)
        self.assertEqual(result.observation_session_id.endpoint, _endpoint())
        self.assertEqual(result.attempts, ())

    def test_failed_start_generation_is_not_reported_as_established(self) -> None:
        bus = InMemoryEventBus()
        observation = _Observation(_endpoint(), bus, ["connection_failed"])
        establishment = AdbDevicesObservationEstablishmentOrchestrator(
            _endpoint(), bus, observation
        )
        result = establishment.establish(
            AdbDevicesObservationEstablishment(
                _endpoint(),
                AdbDevicesObservationEstablishmentPolicy(2.0),
            )
        )
        self.assertIs(result.status, AdbDevicesObservationEstablishmentStatus.FAILED)
        self.assertIs(result.observation_failure, AdbDevicesObservationFailure.SERVER_CONNECTION)
        self.assertIsNone(observation.active_session_id)
        self.assertEqual(result.attempts, ())


class AdbDevicesObservationSupervisorTests(unittest.TestCase):
    def _supervisor(self, outcomes: list[str], *, max_attempts: int | None = None):
        bus = InMemoryEventBus()
        observation = _Observation(_endpoint(), bus, outcomes)
        scheduler = _Scheduler()
        policy = AdbDevicesObservationSupervisionPolicy(
            episode_timeout_seconds=1.0,
            retry_initial_seconds=1,
            retry_max_seconds=8,
            retry_multiplier=2,
            retry_jitter_ratio=0,
            max_attempts=max_attempts,
        )
        supervisor = AdbDevicesObservationSupervisor(
            _endpoint(), bus, observation, scheduler, policy, _random=lambda: 0.5
        )
        return bus, observation, scheduler, supervisor

    def test_start_initializes_observation_through_establishment_episode(self) -> None:
        bus, observation, scheduler, supervisor = self._supervisor(["started"])
        first = supervisor.start()
        self.assertEqual(first.generation, 1)
        self.assertEqual(first.endpoint, _endpoint())
        self.assertEqual(observation.generation, 1)
        self.assertEqual(scheduler.scheduled, [])

    def test_runtime_server_connection_failure_establishes_new_generation(self) -> None:
        bus, observation, scheduler, supervisor = self._supervisor(["started", "started"])
        first = supervisor.start()
        observation.active_session_id = None
        bus.publish(
            AdbDevicesObservationFailed(
                _endpoint(), first, AdbDevicesObservationFailure.SERVER_CONNECTION, "socket lost"
            )
        )
        _wait_until(lambda: observation.generation == 2)
        self.assertEqual(scheduler.scheduled, [])

    def test_establishment_failures_keep_one_cycle_and_exhaust_budget(self) -> None:
        bus, observation, scheduler, supervisor = self._supervisor(
            ["connection_failed", "connection_failed"], max_attempts=2
        )
        exhausted: list[AdbDevicesObservationEstablishmentExhausted] = []
        bus.subscribe(AdbDevicesObservationEstablishmentExhausted, exhausted.append)
        first = supervisor.start()
        self.assertIsNone(first)
        self.assertEqual(observation.generation, 1)
        self.assertEqual(len(scheduler.scheduled), 1)
        delay, retry_event, _ = scheduler.scheduled[0]
        self.assertEqual(delay.total_seconds(), 1.0)
        self.assertIsInstance(retry_event, AdbDevicesObservationEstablishmentRetryDue)
        self.assertEqual(retry_event.endpoint, _endpoint())
        self.assertEqual(retry_event.attempt_number, 2)
        bus.publish(retry_event)
        _wait_until(lambda: len(exhausted) == 1)
        self.assertEqual(observation.generation, 2)
        self.assertEqual(exhausted[0].attempts, 2)
        self.assertEqual(exhausted[0].cycle_id, retry_event.cycle_id)
        self.assertEqual(exhausted[0].endpoint, _endpoint())
        self.assertEqual(len(scheduler.scheduled), 1)

    def test_non_server_connection_failure_does_not_trigger_reestablishment(self) -> None:
        bus, observation, scheduler, supervisor = self._supervisor(["started"])
        first = supervisor.start()
        observation.active_session_id = None
        bus.publish(
            AdbDevicesObservationFailed(
                _endpoint(), first, AdbDevicesObservationFailure.PROTOCOL
            )
        )
        self.assertEqual(observation.generation, 1)
        self.assertEqual(scheduler.scheduled, [])


if __name__ == "__main__":
    unittest.main()
