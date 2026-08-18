from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from random import random
from threading import Lock, Thread, current_thread

from adb.server.endpoint import AdbServerEndpoint
from adb.server.lifecycle import AdbServerEnsureOrchestrator
from adb.supervision.model import (
    AdbTransportInventoryObservationEstablishmentCycleId,
    AdbTransportInventoryObservationSupervisionPolicy,
)
from adb.supervision.signal import (
    AdbTransportInventoryObservationEstablishmentExhausted,
    AdbTransportInventoryObservationEstablishmentRetryDue,
)
from adb.transport.observation.establishment import (
    AdbTransportInventoryObservationEstablishment,
    AdbTransportInventoryObservationEstablishmentOrchestrator,
    AdbTransportInventoryObservationEstablishmentPolicy,
    AdbTransportInventoryObservationEstablishmentResult,
    AdbTransportInventoryObservationEstablishmentStatus,
)
from adb.transport.observation.runner import AdbTransportInventoryObservationController
from adb.transport.observation.signal import (
    AdbTransportInventoryObservationFailed,
    AdbTransportInventoryObservationFailure,
)
from eventing import EventBus, EventSubscriptionToken
from scheduling import ScheduleToken, TemporalScheduler


_RandomSource = Callable[[], float]
_ThreadFactory = Callable[..., Thread]


def _default_thread_factory(*args, **kwargs) -> Thread:
    thread = Thread(*args, **kwargs)
    thread.daemon = True
    return thread


class AdbTransportInventoryObservationSupervisor:
    """Long-lived supervisor for one configured server's transport-inventory observation.

    Startup initialization and runtime server-connection failure both use the same bounded
    observation-establishment episode. Retry/backoff state belongs to one establishment cycle
    and is cleared only after matching ``ObservationStarted`` evidence satisfies an episode.
    A cycle may therefore span multiple observation generations.
    """

    def __init__(
        self,
        endpoint: AdbServerEndpoint,
        event_bus: EventBus,
        observation: AdbTransportInventoryObservationController,
        ensure_orchestrator: AdbServerEnsureOrchestrator,
        scheduler: TemporalScheduler[object],
        policy: AdbTransportInventoryObservationSupervisionPolicy,
        *,
        _random: _RandomSource = random,
        _thread_factory: _ThreadFactory = _default_thread_factory,
    ) -> None:
        if not isinstance(endpoint, AdbServerEndpoint):
            raise TypeError("endpoint must be AdbServerEndpoint")
        if not callable(getattr(event_bus, "publish", None)) or not callable(
            getattr(event_bus, "subscribe", None)
        ):
            raise TypeError("event_bus must satisfy EventBus")
        if not isinstance(observation, AdbTransportInventoryObservationController):
            raise TypeError("observation must satisfy AdbTransportInventoryObservationController")
        if not isinstance(ensure_orchestrator, AdbServerEnsureOrchestrator):
            raise TypeError("ensure_orchestrator must be AdbServerEnsureOrchestrator")
        if not isinstance(scheduler, TemporalScheduler):
            raise TypeError("scheduler must satisfy TemporalScheduler")
        if not isinstance(policy, AdbTransportInventoryObservationSupervisionPolicy):
            raise TypeError(
                "policy must be AdbTransportInventoryObservationSupervisionPolicy"
            )
        self.endpoint = endpoint
        self._bus = event_bus
        self._observation = observation
        self._ensure = ensure_orchestrator
        self._establishment = AdbTransportInventoryObservationEstablishmentOrchestrator(
            endpoint,
            event_bus,
            observation,
            ensure_orchestrator,
        )
        self._scheduler = scheduler
        self._policy = policy
        self._random = _random
        self._thread_factory = _thread_factory
        self._lock = Lock()
        self._subscriptions: tuple[EventSubscriptionToken, ...] = ()
        self._current_session_id = observation.current_session_id
        self._cycle_id: AdbTransportInventoryObservationEstablishmentCycleId | None = None
        self._retry_token: ScheduleToken | None = None
        self._attempt_thread: Thread | None = None
        self._closed = False

    def start(self):
        """Subscribe and establish an initial transport-inventory observation generation.

        Returns the established session id when the first bounded episode succeeds immediately.
        If that episode fails but remains retryable, retry/backoff continues under this supervisor
        and ``None`` is returned.
        """

        with self._lock:
            if self._closed:
                raise RuntimeError("transport-inventory observation supervisor is closed")
            if self._subscriptions:
                raise RuntimeError("transport-inventory observation supervisor is already started")
            failure_token = self._bus.subscribe(
                AdbTransportInventoryObservationFailed,
                self._on_observation_failed,
            )
            retry_token = self._bus.subscribe(
                AdbTransportInventoryObservationEstablishmentRetryDue,
                self._on_retry_due,
            )
            self._subscriptions = (failure_token, retry_token)
            cycle_id = AdbTransportInventoryObservationEstablishmentCycleId.new()
            self._cycle_id = cycle_id

        result = self._establish_once()
        self._handle_establishment_result(cycle_id, 1, result)
        if result.status is AdbTransportInventoryObservationEstablishmentStatus.SATISFIED:
            return result.observation_session_id
        return None

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            subscriptions = self._subscriptions
            self._subscriptions = ()
            retry_token = self._retry_token
            self._retry_token = None
            attempt_thread = self._attempt_thread
            self._cycle_id = None
        for token in subscriptions:
            self._bus.unsubscribe(token)
        if retry_token is not None:
            self._scheduler.cancel(retry_token)
        self._observation.close()
        if attempt_thread is not None and attempt_thread is not current_thread():
            attempt_thread.join()

    def _on_observation_failed(self, event: AdbTransportInventoryObservationFailed) -> None:
        if event.failure is not AdbTransportInventoryObservationFailure.SERVER_CONNECTION:
            return
        if event.session_id.endpoint != self.endpoint:
            return

        with self._lock:
            if self._closed or event.session_id != self._current_session_id:
                return
            if self._cycle_id is not None:
                return
            cycle_id = AdbTransportInventoryObservationEstablishmentCycleId.new()
            self._cycle_id = cycle_id
        self._launch_establishment_attempt(cycle_id, attempt_number=1)

    def _on_retry_due(
        self,
        event: AdbTransportInventoryObservationEstablishmentRetryDue,
    ) -> None:
        if event.endpoint != self.endpoint:
            return
        with self._lock:
            if self._closed or event.cycle_id != self._cycle_id:
                return
            self._retry_token = None
        self._launch_establishment_attempt(event.cycle_id, event.attempt_number)

    def _launch_establishment_attempt(
        self,
        cycle_id: AdbTransportInventoryObservationEstablishmentCycleId,
        attempt_number: int,
    ) -> None:
        thread = self._thread_factory(
            target=self._run_establishment_attempt,
            args=(cycle_id, attempt_number),
            name=(
                "adb-observation-establishment-"
                f"{self.endpoint.host}-{self.endpoint.port}-{attempt_number}"
            ),
        )
        with self._lock:
            if self._closed or self._cycle_id != cycle_id:
                return
            if self._attempt_thread is not None:
                return
            self._attempt_thread = thread
        thread.start()

    def _run_establishment_attempt(
        self,
        cycle_id: AdbTransportInventoryObservationEstablishmentCycleId,
        attempt_number: int,
    ) -> None:
        active = current_thread()
        try:
            result = self._establish_once()
        except BaseException:
            with self._lock:
                if self._attempt_thread is active:
                    self._attempt_thread = None
            raise
        self._handle_establishment_result(
            cycle_id,
            attempt_number,
            result,
            active_thread=active,
        )

    def _establish_once(self) -> AdbTransportInventoryObservationEstablishmentResult:
        return self._establishment.establish(
            AdbTransportInventoryObservationEstablishment(
                self.endpoint,
                AdbTransportInventoryObservationEstablishmentPolicy(
                    self._policy.episode_timeout_seconds,
                    self._policy.ensure_policy,
                ),
            )
        )

    def _handle_establishment_result(
        self,
        cycle_id: AdbTransportInventoryObservationEstablishmentCycleId,
        attempt_number: int,
        result: AdbTransportInventoryObservationEstablishmentResult,
        *,
        active_thread: Thread | None = None,
    ) -> None:
        if result.status is AdbTransportInventoryObservationEstablishmentStatus.SATISFIED:
            session_id = result.observation_session_id
            assert session_id is not None
            self._complete_establishment_cycle(
                cycle_id,
                session_id,
                active_thread=active_thread,
            )
            return

        if active_thread is not None:
            with self._lock:
                if self._attempt_thread is active_thread:
                    self._attempt_thread = None
                if self._closed or self._cycle_id != cycle_id:
                    return

        if self._should_retry(result):
            self._schedule_retry_or_exhaust(cycle_id, attempt_number)
        else:
            self._end_establishment_cycle(cycle_id)

    @staticmethod
    def _should_retry(
        result: AdbTransportInventoryObservationEstablishmentResult,
    ) -> bool:
        failure = result.observation_failure
        return failure in (
            None,
            AdbTransportInventoryObservationFailure.SERVER_CONNECTION,
        )

    def _schedule_retry_or_exhaust(
        self,
        cycle_id: AdbTransportInventoryObservationEstablishmentCycleId,
        attempt_number: int,
    ) -> None:
        max_attempts = self._policy.max_attempts
        if max_attempts is not None and attempt_number >= max_attempts:
            self._end_establishment_cycle(cycle_id)
            self._bus.publish(
                AdbTransportInventoryObservationEstablishmentExhausted(
                    self.endpoint,
                    cycle_id,
                    attempt_number,
                )
            )
            return

        next_attempt = attempt_number + 1
        delay_seconds = self._retry_delay(attempt_number)
        retry_event = AdbTransportInventoryObservationEstablishmentRetryDue(
            self.endpoint,
            cycle_id,
            next_attempt,
        )
        token = self._scheduler.schedule_after(
            timedelta(seconds=delay_seconds),
            retry_event,
        )
        with self._lock:
            if self._closed or self._cycle_id != cycle_id:
                self._scheduler.cancel(token)
                return
            old_token = self._retry_token
            self._retry_token = token
        if old_token is not None:
            self._scheduler.cancel(old_token)

    def _complete_establishment_cycle(
        self,
        cycle_id: AdbTransportInventoryObservationEstablishmentCycleId,
        session_id,
        *,
        active_thread: Thread | None = None,
    ) -> None:
        with self._lock:
            if active_thread is not None and self._attempt_thread is active_thread:
                self._attempt_thread = None
            if self._closed or self._cycle_id != cycle_id:
                return
            retry_token = self._retry_token
            self._retry_token = None
            self._current_session_id = session_id
            self._cycle_id = None
        if retry_token is not None:
            self._scheduler.cancel(retry_token)

    def _end_establishment_cycle(
        self,
        cycle_id: AdbTransportInventoryObservationEstablishmentCycleId,
    ) -> None:
        with self._lock:
            if self._cycle_id != cycle_id:
                return
            retry_token = self._retry_token
            self._retry_token = None
            self._cycle_id = None
        if retry_token is not None:
            self._scheduler.cancel(retry_token)

    def _retry_delay(self, attempt_number: int) -> float:
        base = min(
            self._policy.retry_initial_seconds
            * (self._policy.retry_multiplier ** max(0, attempt_number - 1)),
            self._policy.retry_max_seconds,
        )
        jitter = self._policy.retry_jitter_ratio
        sample = self._random()
        if not 0.0 <= sample <= 1.0:
            raise ValueError(
                "observation supervision random source must return a value in [0, 1]"
            )
        factor = 1.0 + ((sample * 2.0) - 1.0) * jitter
        return max(base * factor, 1e-6)


__all__ = ["AdbTransportInventoryObservationSupervisor"]
