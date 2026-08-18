from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
import math
from numbers import Real
from threading import Condition
from time import monotonic

from adb.server.endpoint import AdbServerEndpoint
from adb.server.lifecycle import (
    AdbServerAvailability,
    AdbServerEnsureAvailable,
    AdbServerEnsurePolicy,
    AdbServerEnsureResult,
    AdbServerEnsureStatus,
    AdbServerProbeResult,
)
from adb.transport.observation.contracts import AdbObservationSessionId
from adb.transport.observation.runner import AdbTransportInventoryObservationController
from adb.transport.observation.signal import (
    AdbTransportInventoryObservationFailed,
    AdbTransportInventoryObservationFailure,
    AdbTransportInventoryObservationStarted,
    AdbTransportInventoryObservationStopped,
)
from eventing import EventBus, EventSubscriptionToken
from native_attempt import NativeAttemptResult


_MonotonicClock = Callable[[], float]


def _normalize_positive_seconds(value: object, *, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{field_name} must be a real number")
    normalized = float(value)
    if not math.isfinite(normalized) or normalized <= 0.0:
        raise ValueError(f"{field_name} must be finite and greater than zero")
    return normalized


def _normalize_optional_text(value: object, *, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string or None")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} cannot be empty")
    return normalized


class AdbTransportInventoryObservationEstablishmentStatus(str, Enum):
    """Terminal status of one bounded transport-inventory observation establishment episode."""

    SATISFIED = "satisfied"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


@dataclass(frozen=True, slots=True)
class AdbTransportInventoryObservationEstablishmentPolicy:
    """Bound one observation-establishment episode with explicit server-ensure policy."""

    timeout_seconds: float
    ensure_policy: AdbServerEnsurePolicy

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "timeout_seconds",
            _normalize_positive_seconds(
                self.timeout_seconds,
                field_name="ADB transport-inventory observation establishment timeout",
            ),
        )
        if not isinstance(self.ensure_policy, AdbServerEnsurePolicy):
            raise TypeError("ensure_policy must be AdbServerEnsurePolicy")


@dataclass(frozen=True, slots=True)
class AdbTransportInventoryObservationEstablishment:
    """Request establishment of one configured server's transport-inventory observation."""

    endpoint: AdbServerEndpoint
    policy: AdbTransportInventoryObservationEstablishmentPolicy

    def __post_init__(self) -> None:
        if not isinstance(self.endpoint, AdbServerEndpoint):
            raise TypeError("endpoint must be AdbServerEndpoint")
        if not isinstance(
            self.policy,
            AdbTransportInventoryObservationEstablishmentPolicy,
        ):
            raise TypeError(
                "policy must be AdbTransportInventoryObservationEstablishmentPolicy"
            )


@dataclass(frozen=True, slots=True)
class AdbTransportInventoryObservationEstablishmentResult:
    """Evidence from one bounded transport-inventory observation establishment episode."""

    operation: AdbTransportInventoryObservationEstablishment
    status: AdbTransportInventoryObservationEstablishmentStatus
    initial_probe: AdbServerProbeResult
    ensure_result: AdbServerEnsureResult | None = None
    observation_session_id: AdbObservationSessionId | None = None
    observation_failure: AdbTransportInventoryObservationFailure | None = None
    diagnostic: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(
            self.operation,
            AdbTransportInventoryObservationEstablishment,
        ):
            raise TypeError(
                "operation must be AdbTransportInventoryObservationEstablishment"
            )
        if not isinstance(
            self.status,
            AdbTransportInventoryObservationEstablishmentStatus,
        ):
            raise TypeError(
                "status must be AdbTransportInventoryObservationEstablishmentStatus"
            )
        if not isinstance(self.initial_probe, AdbServerProbeResult):
            raise TypeError("initial_probe must be AdbServerProbeResult")
        if self.initial_probe.endpoint != self.operation.endpoint:
            raise ValueError("initial probe endpoint must match establishment operation")
        if self.ensure_result is not None and not isinstance(
            self.ensure_result, AdbServerEnsureResult
        ):
            raise TypeError("ensure_result must be AdbServerEnsureResult or None")
        if self.observation_session_id is not None:
            if not isinstance(self.observation_session_id, AdbObservationSessionId):
                raise TypeError("observation_session_id must be AdbObservationSessionId or None")
            if self.observation_session_id.endpoint != self.operation.endpoint:
                raise ValueError(
                    "observation session endpoint must match establishment operation"
                )
        if self.observation_failure is not None and not isinstance(
            self.observation_failure,
            AdbTransportInventoryObservationFailure,
        ):
            raise TypeError(
                "observation_failure must be AdbTransportInventoryObservationFailure or None"
            )
        if (
            self.status
            is AdbTransportInventoryObservationEstablishmentStatus.SATISFIED
        ):
            if self.observation_session_id is None:
                raise ValueError(
                    "satisfied establishment result requires observation_session_id"
                )
            if self.observation_failure is not None:
                raise ValueError(
                    "satisfied establishment result cannot carry observation_failure"
                )
        object.__setattr__(
            self,
            "diagnostic",
            _normalize_optional_text(
                self.diagnostic,
                field_name="ADB transport-inventory observation establishment diagnostic",
            ),
        )

    @property
    def attempts(self) -> tuple[NativeAttemptResult, ...]:
        return self.ensure_result.attempts if self.ensure_result is not None else ()

    @property
    def final_probe(self) -> AdbServerProbeResult:
        return (
            self.ensure_result.final_probe
            if self.ensure_result is not None
            else self.initial_probe
        )


class AdbTransportInventoryObservationEstablishmentOrchestrator:
    """Establish one track-devices observation generation inside a bounded episode.

    The episode owns no retry/backoff state. Satisfaction requires matching
    ``AdbTransportInventoryObservationStarted`` evidence, not merely acceptance of
    ``observation.start()``. Server ensure is a sub-step only when the configured server is
    freshly observed as unavailable.
    """

    def __init__(
        self,
        endpoint: AdbServerEndpoint,
        event_bus: EventBus,
        observation: AdbTransportInventoryObservationController,
        ensure_orchestrator: object,
        *,
        _monotonic: _MonotonicClock = monotonic,
    ) -> None:
        if not isinstance(endpoint, AdbServerEndpoint):
            raise TypeError("endpoint must be AdbServerEndpoint")
        if not callable(getattr(event_bus, "subscribe", None)) or not callable(
            getattr(event_bus, "unsubscribe", None)
        ):
            raise TypeError("event_bus must satisfy EventBus")
        if not isinstance(observation, AdbTransportInventoryObservationController):
            raise TypeError("observation must satisfy observation controller")
        if not callable(getattr(ensure_orchestrator, "probe", None)) or not callable(
            getattr(ensure_orchestrator, "ensure", None)
        ):
            raise TypeError("ensure_orchestrator must provide probe() and ensure()")
        self.endpoint = endpoint
        self._bus = event_bus
        self._observation = observation
        self._ensure = ensure_orchestrator
        self._monotonic = _monotonic

    def establish(
        self,
        operation: AdbTransportInventoryObservationEstablishment,
    ) -> AdbTransportInventoryObservationEstablishmentResult:
        if not isinstance(
            operation,
            AdbTransportInventoryObservationEstablishment,
        ):
            raise TypeError(
                "operation must be AdbTransportInventoryObservationEstablishment"
            )
        if operation.endpoint != self.endpoint:
            raise ValueError("operation endpoint does not match configured ADB server endpoint")

        deadline = self._monotonic() + operation.policy.timeout_seconds
        condition = Condition()
        events: deque[object] = deque()

        def collect(event: object) -> None:
            with condition:
                events.append(event)
                condition.notify()

        subscriptions = self._subscribe(collect)
        try:
            return self._run_episode(operation, deadline, condition, events)
        finally:
            for token in subscriptions:
                self._bus.unsubscribe(token)

    def _run_episode(
        self,
        operation: AdbTransportInventoryObservationEstablishment,
        deadline: float,
        condition: Condition,
        events: deque[object],
    ) -> AdbTransportInventoryObservationEstablishmentResult:
        initial_probe = self._ensure.probe()
        ensure_result: AdbServerEnsureResult | None = None

        if initial_probe.availability is AdbServerAvailability.INDETERMINATE:
            return self._complete(
                operation,
                AdbTransportInventoryObservationEstablishmentStatus.FAILED,
                initial_probe,
                diagnostic=initial_probe.diagnostic or "ADB server availability is indeterminate",
            )

        if initial_probe.availability is AdbServerAvailability.UNAVAILABLE:
            remaining = deadline - self._monotonic()
            if remaining <= 0.0:
                return self._complete(
                    operation,
                    AdbTransportInventoryObservationEstablishmentStatus.TIMED_OUT,
                    initial_probe,
                    diagnostic="establishment deadline expired before server ensure",
                )
            requested = operation.policy.ensure_policy
            bounded_policy = AdbServerEnsurePolicy(
                min(requested.timeout_seconds, remaining),
                requested.probe_interval_seconds,
            )
            ensure_result = self._ensure.ensure(
                AdbServerEnsureAvailable(operation.endpoint, bounded_policy)
            )
            if ensure_result.status is not AdbServerEnsureStatus.SATISFIED:
                status = (
                    AdbTransportInventoryObservationEstablishmentStatus.TIMED_OUT
                    if ensure_result.status is AdbServerEnsureStatus.TIMED_OUT
                    else AdbTransportInventoryObservationEstablishmentStatus.FAILED
                )
                return self._complete(
                    operation,
                    status,
                    initial_probe,
                    ensure_result=ensure_result,
                    diagnostic=(
                        ensure_result.final_probe.diagnostic
                        or "ADB server could not be established as available"
                    ),
                )

        if deadline - self._monotonic() <= 0.0:
            return self._complete(
                operation,
                AdbTransportInventoryObservationEstablishmentStatus.TIMED_OUT,
                initial_probe,
                ensure_result=ensure_result,
                diagnostic="establishment deadline expired before observation start",
            )

        try:
            session_id = self._observation.start()
        except RuntimeError as exc:
            return self._complete(
                operation,
                AdbTransportInventoryObservationEstablishmentStatus.FAILED,
                initial_probe,
                ensure_result=ensure_result,
                diagnostic=str(exc),
            )
        if session_id.endpoint != operation.endpoint:
            raise ValueError("started observation belongs to another ADB server endpoint")

        while True:
            event = self._next_event(condition, events, deadline)
            if event is None:
                return self._complete(
                    operation,
                    AdbTransportInventoryObservationEstablishmentStatus.TIMED_OUT,
                    initial_probe,
                    ensure_result=ensure_result,
                    observation_session_id=session_id,
                    diagnostic="timed out waiting for observation establishment evidence",
                )

            event_session = getattr(event, "session_id", None)
            if event_session != session_id:
                continue
            if isinstance(event, AdbTransportInventoryObservationStarted):
                return self._complete(
                    operation,
                    AdbTransportInventoryObservationEstablishmentStatus.SATISFIED,
                    initial_probe,
                    ensure_result=ensure_result,
                    observation_session_id=session_id,
                )
            if isinstance(event, AdbTransportInventoryObservationFailed):
                return self._complete(
                    operation,
                    AdbTransportInventoryObservationEstablishmentStatus.FAILED,
                    initial_probe,
                    ensure_result=ensure_result,
                    observation_session_id=session_id,
                    observation_failure=event.failure,
                    diagnostic=(
                        event.diagnostic or f"observation failed: {event.failure.value}"
                    ),
                )
            if isinstance(event, AdbTransportInventoryObservationStopped):
                return self._complete(
                    operation,
                    AdbTransportInventoryObservationEstablishmentStatus.FAILED,
                    initial_probe,
                    ensure_result=ensure_result,
                    observation_session_id=session_id,
                    diagnostic="observation stopped before establishment",
                )

    def _subscribe(
        self,
        collect: Callable[[object], None],
    ) -> tuple[EventSubscriptionToken, ...]:
        return (
            self._bus.subscribe(AdbTransportInventoryObservationStarted, collect),
            self._bus.subscribe(AdbTransportInventoryObservationFailed, collect),
            self._bus.subscribe(AdbTransportInventoryObservationStopped, collect),
        )

    def _next_event(
        self,
        condition: Condition,
        events: deque[object],
        deadline: float,
    ) -> object | None:
        with condition:
            while not events:
                remaining = deadline - self._monotonic()
                if remaining <= 0.0:
                    return None
                condition.wait(timeout=remaining)
            return events.popleft()

    @staticmethod
    def _complete(
        operation: AdbTransportInventoryObservationEstablishment,
        status: AdbTransportInventoryObservationEstablishmentStatus,
        initial_probe: AdbServerProbeResult,
        *,
        ensure_result: AdbServerEnsureResult | None = None,
        observation_session_id: AdbObservationSessionId | None = None,
        observation_failure: AdbTransportInventoryObservationFailure | None = None,
        diagnostic: str | None = None,
    ) -> AdbTransportInventoryObservationEstablishmentResult:
        return AdbTransportInventoryObservationEstablishmentResult(
            operation=operation,
            status=status,
            initial_probe=initial_probe,
            ensure_result=ensure_result,
            observation_session_id=observation_session_id,
            observation_failure=observation_failure,
            diagnostic=diagnostic,
        )


__all__ = [
    "AdbTransportInventoryObservationEstablishment",
    "AdbTransportInventoryObservationEstablishmentOrchestrator",
    "AdbTransportInventoryObservationEstablishmentPolicy",
    "AdbTransportInventoryObservationEstablishmentResult",
    "AdbTransportInventoryObservationEstablishmentStatus",
]
