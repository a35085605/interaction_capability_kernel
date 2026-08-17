from __future__ import annotations

from datetime import datetime, timezone
import time
import unittest

from adb.configuration import AdbServerConfiguration, AdbServerId
from adb.errors import AdbServerConnectionError
from adb.server import AdbServerEndpoint, AdbServerStatus
from adb.server.lifecycle import (
    AdbServerEnsureAvailable,
    AdbServerEnsureOrchestrator,
    AdbServerEnsurePolicy,
    AdbServerEnsureStatus,
)
from adb.server.signal import (
    AdbServerCommandCompleted,
    AdbServerEnsureCompleted,
    AdbServerProbeCompleted,
)
from adb.supervision import (
    AdbTransportInventoryObservationEstablishmentExhausted,
    AdbTransportInventoryObservationEstablishmentRetryDue,
    AdbTransportInventoryObservationSupervisionPolicy,
    AdbTransportInventoryObservationSupervisor,
)
from adb.transport.observation.contracts import AdbObservationSessionId
from adb.transport.observation.establishment import (
    AdbTransportInventoryObservationEstablishment,
    AdbTransportInventoryObservationEstablishmentOrchestrator,
    AdbTransportInventoryObservationEstablishmentPolicy,
    AdbTransportInventoryObservationEstablishmentStatus,
)
from adb.transport.observation.signal import (
    AdbTransportInventoryObservationFailed,
    AdbTransportInventoryObservationFailure,
    AdbTransportInventoryObservationStarted,
)
from eventing.adapters import InMemoryEventBus
from native_attempt import (
    NativeAttemptResult,
    NativeAttemptStatus,
    NativeCompletionScope,
)
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
    def __init__(
        self,
        configuration: AdbServerConfiguration,
        bus: InMemoryEventBus,
        outcomes: list[str],
    ) -> None:
        self.configuration = configuration
        self.bus = bus
        self.outcomes = outcomes
        self.generation = 0
        self.current_session_id = None
        self.closed = False
        self.stop_calls = 0

    def start(self) -> AdbObservationSessionId:
        self.generation += 1
        self.current_session_id = AdbObservationSessionId(
            self.configuration.server_id,
            self.generation,
        )
        outcome = self.outcomes.pop(0)
        if outcome == "started":
            self.bus.publish(
                AdbTransportInventoryObservationStarted(
                    self.configuration.endpoint,
                    self.current_session_id,
                )
            )
        elif outcome == "connection_failed":
            self.bus.publish(
                AdbTransportInventoryObservationFailed(
                    self.configuration.endpoint,
                    self.current_session_id,
                    AdbTransportInventoryObservationFailure.SERVER_CONNECTION,
                    "connection failed",
                )
            )
        elif outcome == "protocol_failed":
            self.bus.publish(
                AdbTransportInventoryObservationFailed(
                    self.configuration.endpoint,
                    self.current_session_id,
                    AdbTransportInventoryObservationFailure.PROTOCOL,
                    "protocol failed",
                )
            )
        else:
            raise AssertionError(f"unsupported observation outcome: {outcome}")
        return self.current_session_id

    def stop(self) -> None:
        self.stop_calls += 1

    def close(self) -> None:
        self.closed = True


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


def _configuration() -> AdbServerConfiguration:
    return AdbServerConfiguration(
        AdbServerId("local-main"),
        AdbServerEndpoint("127.0.0.1", 5037),
    )


def _attempt(status: NativeAttemptStatus = NativeAttemptStatus.SUCCEEDED) -> NativeAttemptResult:
    now = datetime(2026, 8, 17, tzinfo=timezone.utc)
    return NativeAttemptResult(
        status=status,
        completion_scope=(
            NativeCompletionScope.PROCESS_EXIT
            if status is NativeAttemptStatus.SUCCEEDED
            else None
        ),
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
        reader = _StatusReader(
            [AdbServerConnectionError("refused"), AdbServerStatus(version="0010")]
        )
        commands = _ServerCommands(_attempt())
        clock = _Clock()
        orchestrator = AdbServerEnsureOrchestrator(
            _configuration(),
            reader,
            commands,
            commands,
            bus,
            _monotonic=clock.monotonic,
            _sleep=clock.sleep,
        )

        result = orchestrator.ensure(
            AdbServerEnsureAvailable(
                _configuration().server_id,
                AdbServerEnsurePolicy(1, 0.1),
            )
        )

        self.assertIs(result.status, AdbServerEnsureStatus.SATISFIED)
        self.assertEqual(len(commands.started), 1)
        self.assertEqual(
            [type(signal) for signal in signals],
            [
                AdbServerProbeCompleted,
                AdbServerCommandCompleted,
                AdbServerProbeCompleted,
                AdbServerEnsureCompleted,
            ],
        )

    def test_already_available_does_not_issue_native_command(self) -> None:
        bus = InMemoryEventBus()
        reader = _StatusReader([AdbServerStatus()])
        commands = _ServerCommands(_attempt())
        orchestrator = AdbServerEnsureOrchestrator(
            _configuration(), reader, commands, commands, bus
        )

        result = orchestrator.ensure(
            AdbServerEnsureAvailable(
                _configuration().server_id,
                AdbServerEnsurePolicy(1, 0.1),
            )
        )

        self.assertIs(result.status, AdbServerEnsureStatus.SATISFIED)
        self.assertEqual(result.attempts, ())
        self.assertEqual(commands.started, [])

    def test_unsatisfied_ensure_times_out_after_fresh_verification(self) -> None:
        bus = InMemoryEventBus()
        reader = _StatusReader([AdbServerConnectionError("down")], repeat_last=True)
        commands = _ServerCommands(_attempt())
        clock = _Clock()
        orchestrator = AdbServerEnsureOrchestrator(
            _configuration(),
            reader,
            commands,
            commands,
            bus,
            _monotonic=clock.monotonic,
            _sleep=clock.sleep,
        )

        result = orchestrator.ensure(
            AdbServerEnsureAvailable(
                _configuration().server_id,
                AdbServerEnsurePolicy(0.2, 0.1),
            )
        )

        self.assertIs(result.status, AdbServerEnsureStatus.TIMED_OUT)
        self.assertGreaterEqual(reader.calls, 3)
        self.assertEqual(len(result.attempts), 1)


class AdbTransportInventoryObservationEstablishmentTests(unittest.TestCase):
    def test_establishment_requires_started_evidence_after_server_ensure(self) -> None:
        bus = InMemoryEventBus()
        reader = _StatusReader(
            [
                AdbServerConnectionError("down"),
                AdbServerConnectionError("down"),
                AdbServerStatus(),
            ]
        )
        commands = _ServerCommands(_attempt())
        observation = _Observation(_configuration(), bus, ["started"])
        ensure = AdbServerEnsureOrchestrator(
            _configuration(), reader, commands, commands, bus
        )
        establishment = AdbTransportInventoryObservationEstablishmentOrchestrator(
            _configuration(), bus, observation, ensure
        )

        result = establishment.establish(
            AdbTransportInventoryObservationEstablishment(
                _configuration().server_id,
                AdbTransportInventoryObservationEstablishmentPolicy(
                    2.0,
                    AdbServerEnsurePolicy(1.0, 0.1),
                ),
            )
        )

        self.assertIs(
            result.status,
            AdbTransportInventoryObservationEstablishmentStatus.SATISFIED,
        )
        self.assertEqual(result.observation_session_id.generation, 1)
        self.assertEqual(len(result.attempts), 1)
        self.assertEqual(len(commands.started), 1)

    def test_failed_start_generation_is_not_reported_as_established(self) -> None:
        bus = InMemoryEventBus()
        reader = _StatusReader([AdbServerStatus()])
        commands = _ServerCommands(_attempt())
        observation = _Observation(_configuration(), bus, ["connection_failed"])
        ensure = AdbServerEnsureOrchestrator(
            _configuration(), reader, commands, commands, bus
        )
        establishment = AdbTransportInventoryObservationEstablishmentOrchestrator(
            _configuration(), bus, observation, ensure
        )

        result = establishment.establish(
            AdbTransportInventoryObservationEstablishment(
                _configuration().server_id,
                AdbTransportInventoryObservationEstablishmentPolicy(
                    2.0,
                    AdbServerEnsurePolicy(1.0, 0.1),
                ),
            )
        )

        self.assertIs(
            result.status,
            AdbTransportInventoryObservationEstablishmentStatus.FAILED,
        )
        self.assertIs(
            result.observation_failure,
            AdbTransportInventoryObservationFailure.SERVER_CONNECTION,
        )


class AdbTransportInventoryObservationSupervisorTests(unittest.TestCase):
    def _supervisor(
        self,
        reader: _StatusReader,
        commands: _ServerCommands,
        outcomes: list[str],
        *,
        max_attempts: int | None = None,
    ):
        bus = InMemoryEventBus()
        observation = _Observation(_configuration(), bus, outcomes)
        scheduler = _Scheduler()
        clock = _Clock()
        ensure = AdbServerEnsureOrchestrator(
            _configuration(),
            reader,
            commands,
            commands,
            bus,
            _monotonic=clock.monotonic,
            _sleep=clock.sleep,
        )
        policy = AdbTransportInventoryObservationSupervisionPolicy(
            ensure_policy=AdbServerEnsurePolicy(0.2, 0.1),
            episode_timeout_seconds=1.0,
            retry_initial_seconds=1,
            retry_max_seconds=8,
            retry_multiplier=2,
            retry_jitter_ratio=0,
            max_attempts=max_attempts,
        )
        supervisor = AdbTransportInventoryObservationSupervisor(
            _configuration(),
            bus,
            observation,
            ensure,
            scheduler,
            policy,
            _random=lambda: 0.5,
        )
        return bus, observation, scheduler, supervisor

    def test_start_initializes_observation_through_establishment_episode(self) -> None:
        reader = _StatusReader([AdbServerStatus()])
        commands = _ServerCommands(_attempt())
        bus, observation, scheduler, supervisor = self._supervisor(
            reader, commands, ["started"]
        )

        first = supervisor.start()

        self.assertEqual(first.generation, 1)
        self.assertEqual(observation.generation, 1)
        self.assertEqual(commands.started, [])
        self.assertEqual(scheduler.scheduled, [])

    def test_runtime_server_connection_failure_establishes_new_generation(self) -> None:
        reader = _StatusReader([AdbServerStatus()], repeat_last=True)
        commands = _ServerCommands(_attempt())
        bus, observation, scheduler, supervisor = self._supervisor(
            reader, commands, ["started", "started"]
        )
        first = supervisor.start()

        bus.publish(
            AdbTransportInventoryObservationFailed(
                _configuration().endpoint,
                first,
                AdbTransportInventoryObservationFailure.SERVER_CONNECTION,
                "socket lost",
            )
        )
        _wait_until(lambda: observation.generation == 2)

        self.assertEqual(commands.started, [])
        self.assertEqual(scheduler.scheduled, [])

    def test_establishment_failures_keep_one_cycle_and_exhaust_budget(self) -> None:
        reader = _StatusReader([AdbServerStatus()], repeat_last=True)
        commands = _ServerCommands(_attempt())
        bus, observation, scheduler, supervisor = self._supervisor(
            reader,
            commands,
            ["connection_failed", "connection_failed"],
            max_attempts=2,
        )
        exhausted: list[AdbTransportInventoryObservationEstablishmentExhausted] = []
        bus.subscribe(
            AdbTransportInventoryObservationEstablishmentExhausted,
            exhausted.append,
        )

        first = supervisor.start()

        self.assertIsNone(first)
        self.assertEqual(observation.generation, 1)
        self.assertEqual(len(scheduler.scheduled), 1)
        delay, retry_event, _ = scheduler.scheduled[0]
        self.assertEqual(delay.total_seconds(), 1.0)
        self.assertIsInstance(
            retry_event,
            AdbTransportInventoryObservationEstablishmentRetryDue,
        )
        self.assertEqual(retry_event.attempt_number, 2)

        bus.publish(retry_event)
        _wait_until(lambda: len(exhausted) == 1)

        self.assertEqual(observation.generation, 2)
        self.assertEqual(exhausted[0].attempts, 2)
        self.assertEqual(exhausted[0].cycle_id, retry_event.cycle_id)
        self.assertEqual(len(scheduler.scheduled), 1)

    def test_non_server_connection_failure_does_not_trigger_reestablishment(self) -> None:
        reader = _StatusReader([AdbServerStatus()])
        commands = _ServerCommands(_attempt())
        bus, observation, scheduler, supervisor = self._supervisor(
            reader, commands, ["started"]
        )
        first = supervisor.start()
        calls_after_initialization = reader.calls

        bus.publish(
            AdbTransportInventoryObservationFailed(
                _configuration().endpoint,
                first,
                AdbTransportInventoryObservationFailure.PROTOCOL,
            )
        )

        self.assertEqual(observation.generation, 1)
        self.assertEqual(reader.calls, calls_after_initialization)
        self.assertEqual(commands.started, [])
        self.assertEqual(scheduler.scheduled, [])


if __name__ == "__main__":
    unittest.main()
