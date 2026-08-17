from __future__ import annotations

from collections import deque
from collections.abc import Callable
from threading import Condition
from time import monotonic

from adb.configuration import AdbServerConfiguration
from adb.errors import AdbError
from adb.transport.binding import (
    AdbTransportBindingConfiguration,
    AdbTransportBindingResolutionStatus,
    resolve_transport_binding,
)
from adb.transport.connection import AdbTcpConnect, AdbTcpConnector
from adb.transport.inventory.domain import AdbDevicesSnapshot, AdbTrackedDevice
from adb.transport.inventory.query import AdbDevicesSnapshotReader
from adb.transport.observation.contracts import AdbObservationSessionId
from adb.transport.observation.runner import AdbTransportInventoryObservationController
from adb.transport.observation.signal import (
    AdbTransportInventoryObservationFailed,
    AdbTransportInventoryObservationStarted,
    AdbTransportInventoryObservationStopped,
    AdbTransportInventorySnapshotObserved,
)
from adb.transport.orchestration import (
    AdbTransportPreparation,
    AdbTransportPreparationPolicy,
    AdbTransportPreparationResult,
    AdbTransportPreparationSatisfaction,
    AdbTransportPreparationStatus,
    AdbTransportPresenceSatisfaction,
)
from adb.transport.selection import AdbTransportId
from adb.transport.signal import (
    AdbTransportCommandCompleted,
    AdbTransportPreparationCompleted,
)
from eventing import EventBus, EventSubscriptionToken
from native_attempt import NativeAttemptResult, NativeAttemptStatus


_MonotonicClock = Callable[[], float]


class AdbTransportPreparationOrchestrator:
    """Run presence and state gates inside one generation-fenced preparation episode.

    The observation session is caller-owned and must already be active. The orchestrator
    subscribes before taking its one-shot inventory snapshot, so state updates arriving during
    the initial probe or atomic connect attempt remain part of the same episode.
    """

    def __init__(
        self,
        server_configuration: AdbServerConfiguration,
        binding_configuration: AdbTransportBindingConfiguration,
        snapshot_reader: AdbDevicesSnapshotReader,
        connector: AdbTcpConnector,
        event_bus: EventBus,
        observation: AdbTransportInventoryObservationController,
        *,
        _monotonic: _MonotonicClock = monotonic,
    ) -> None:
        if not isinstance(server_configuration, AdbServerConfiguration):
            raise TypeError("server_configuration must be AdbServerConfiguration")
        if not isinstance(binding_configuration, AdbTransportBindingConfiguration):
            raise TypeError("binding_configuration must be AdbTransportBindingConfiguration")
        if binding_configuration.server_id != server_configuration.server_id:
            raise ValueError("binding configuration server_id does not match ADB server")
        if not callable(getattr(snapshot_reader, "read", None)):
            raise TypeError("snapshot_reader must provide read()")
        if not callable(getattr(connector, "connect", None)):
            raise TypeError("connector must provide connect()")
        if not callable(getattr(event_bus, "publish", None)) or not callable(
            getattr(event_bus, "subscribe", None)
        ) or not callable(getattr(event_bus, "unsubscribe", None)):
            raise TypeError("event_bus must satisfy EventBus")
        if not isinstance(observation, AdbTransportInventoryObservationController):
            raise TypeError("observation must satisfy observation controller")
        self.server_configuration = server_configuration
        self.binding_configuration = binding_configuration
        self._snapshot_reader = snapshot_reader
        self._connector = connector
        self._bus = event_bus
        self._observation = observation
        self._monotonic = _monotonic

    def prepare(
        self,
        operation: AdbTransportPreparation,
        policy: AdbTransportPreparationPolicy,
    ) -> AdbTransportPreparationResult:
        if not isinstance(operation, AdbTransportPreparation):
            raise TypeError("operation must be AdbTransportPreparation")
        if not isinstance(policy, AdbTransportPreparationPolicy):
            raise TypeError("policy must be AdbTransportPreparationPolicy")
        if operation.server_id != self.server_configuration.server_id:
            raise ValueError("operation server_id does not match configured ADB server")
        if operation.binding_id != self.binding_configuration.binding_id:
            raise ValueError("operation binding_id does not match configured ADB binding")

        session_id = self._observation.current_session_id
        if session_id is None:
            raise RuntimeError("transport preparation requires an active observation session")
        if session_id.server_id != operation.server_id:
            raise ValueError("active observation session belongs to another ADB server")

        deadline = self._monotonic() + policy.timeout_seconds
        condition = Condition()
        events: deque[object] = deque()

        def collect(event: object) -> None:
            with condition:
                events.append(event)
                condition.notify()

        subscriptions = self._subscribe(collect)
        try:
            return self._run_episode(
                operation,
                policy,
                session_id,
                deadline,
                condition,
                events,
            )
        finally:
            for token in subscriptions:
                self._bus.unsubscribe(token)

    def _subscribe(self, collect: Callable[[object], None]) -> tuple[EventSubscriptionToken, ...]:
        return (
            self._bus.subscribe(AdbTransportInventorySnapshotObserved, collect),
            self._bus.subscribe(AdbTransportInventoryObservationFailed, collect),
            self._bus.subscribe(AdbTransportInventoryObservationStopped, collect),
            self._bus.subscribe(AdbTransportInventoryObservationStarted, collect),
        )

    def _run_episode(
        self,
        operation: AdbTransportPreparation,
        policy: AdbTransportPreparationPolicy,
        session_id: AdbObservationSessionId,
        deadline: float,
        condition: Condition,
        events: deque[object],
    ) -> AdbTransportPreparationResult:
        attempts: list[NativeAttemptResult] = []
        presence: AdbTransportPresenceSatisfaction | None = None
        pinned_id: AdbTransportId | None = None
        final_snapshot: AdbDevicesSnapshot | None = None
        final_row: AdbTrackedDevice | None = None
        initial_snapshot_processed = False
        connect_attempted = False
        diagnostic: str | None = None

        try:
            snapshot = self._snapshot_reader.read(self.server_configuration.endpoint)
        except AdbError as exc:
            diagnostic = str(exc) or exc.__class__.__name__
        else:
            initial_snapshot_processed = True
            final_snapshot = snapshot
            outcome = self._evaluate_snapshot(
                snapshot,
                policy,
                pinned_id,
                presence,
                initial=True,
            )
            presence, pinned_id, final_row, terminal = outcome
            if terminal is not None:
                return self._complete(
                    operation,
                    policy,
                    session_id,
                    terminal,
                    attempts,
                    presence,
                    final_snapshot,
                    final_row,
                    pinned_id,
                    diagnostic,
                    already_satisfied=(
                        terminal is AdbTransportPreparationStatus.SATISFIED
                    ),
                )
            if presence is None and self.binding_configuration.connect_address is not None:
                connect_attempted = True
                attempts.append(self._connect())

        while True:
            if not initial_snapshot_processed and not connect_attempted:
                # An indeterminate one-shot query does not prove absence, so wait for the
                # generation-fenced observation stream before deciding whether to connect.
                pass

            event = self._next_event(condition, events, deadline)
            if event is None:
                terminal = (
                    AdbTransportPreparationStatus.FAILED
                    if attempts and attempts[-1].status is NativeAttemptStatus.FAILED
                    else AdbTransportPreparationStatus.TIMED_OUT
                )
                return self._complete(
                    operation,
                    policy,
                    session_id,
                    terminal,
                    attempts,
                    presence,
                    final_snapshot,
                    final_row,
                    pinned_id,
                    diagnostic,
                )

            event_session = getattr(event, "session_id", None)
            if isinstance(event_session, AdbObservationSessionId):
                if event_session.server_id != session_id.server_id:
                    continue
                if event_session.generation < session_id.generation:
                    continue
                if event_session.generation > session_id.generation:
                    return self._complete(
                        operation,
                        policy,
                        session_id,
                        AdbTransportPreparationStatus.OBSERVATION_REPLACED,
                        attempts,
                        presence,
                        final_snapshot,
                        final_row,
                        pinned_id,
                        "transport inventory observation generation changed",
                    )

            if isinstance(event, AdbTransportInventoryObservationFailed):
                return self._complete(
                    operation,
                    policy,
                    session_id,
                    AdbTransportPreparationStatus.OBSERVATION_FAILED,
                    attempts,
                    presence,
                    final_snapshot,
                    final_row,
                    pinned_id,
                    event.diagnostic or f"observation failed: {event.failure.value}",
                )
            if isinstance(event, AdbTransportInventoryObservationStopped):
                return self._complete(
                    operation,
                    policy,
                    session_id,
                    AdbTransportPreparationStatus.OBSERVATION_STOPPED,
                    attempts,
                    presence,
                    final_snapshot,
                    final_row,
                    pinned_id,
                    "transport inventory observation stopped",
                )
            if isinstance(event, AdbTransportInventoryObservationStarted):
                continue
            if not isinstance(event, AdbTransportInventorySnapshotObserved):
                continue

            final_snapshot = event.snapshot
            outcome = self._evaluate_snapshot(
                event.snapshot,
                policy,
                pinned_id,
                presence,
                initial=False,
            )
            presence, pinned_id, final_row, terminal = outcome
            initial_snapshot_processed = True
            if terminal is not None:
                return self._complete(
                    operation,
                    policy,
                    session_id,
                    terminal,
                    attempts,
                    presence,
                    final_snapshot,
                    final_row,
                    pinned_id,
                    diagnostic,
                )
            if (
                presence is None
                and not connect_attempted
                and self.binding_configuration.connect_address is not None
            ):
                connect_attempted = True
                attempts.append(self._connect())

    def _evaluate_snapshot(
        self,
        snapshot: AdbDevicesSnapshot,
        policy: AdbTransportPreparationPolicy,
        pinned_id: AdbTransportId | None,
        presence: AdbTransportPresenceSatisfaction | None,
        *,
        initial: bool,
    ) -> tuple[
        AdbTransportPresenceSatisfaction | None,
        AdbTransportId | None,
        AdbTrackedDevice | None,
        AdbTransportPreparationStatus | None,
    ]:
        resolution = resolve_transport_binding(self.binding_configuration, snapshot)

        if pinned_id is not None:
            pinned_matches = tuple(
                row for row in snapshot.devices if row.transport_id == pinned_id
            )
            if len(pinned_matches) > 1:
                return presence, pinned_id, None, AdbTransportPreparationStatus.AMBIGUOUS
            if not pinned_matches:
                if resolution.status is AdbTransportBindingResolutionStatus.RESOLVED:
                    replacement = resolution.row
                    assert replacement is not None
                    if replacement.transport_id != pinned_id:
                        return (
                            presence,
                            pinned_id,
                            replacement,
                            AdbTransportPreparationStatus.TRANSPORT_REPLACED,
                        )
                if resolution.status is AdbTransportBindingResolutionStatus.AMBIGUOUS:
                    return presence, pinned_id, None, AdbTransportPreparationStatus.AMBIGUOUS
                return presence, pinned_id, None, AdbTransportPreparationStatus.TRANSPORT_LOST
            row = pinned_matches[0]
        else:
            if resolution.status is AdbTransportBindingResolutionStatus.AMBIGUOUS:
                return presence, None, None, AdbTransportPreparationStatus.AMBIGUOUS
            if resolution.status is AdbTransportBindingResolutionStatus.ABSENT:
                return presence, None, None, None
            row = resolution.row
            assert row is not None
            if presence is None:
                presence = (
                    AdbTransportPresenceSatisfaction.ALREADY_PRESENT
                    if initial
                    else AdbTransportPresenceSatisfaction.OBSERVED
                )
            if isinstance(row.transport_id, AdbTransportId):
                pinned_id = row.transport_id

        if row.state in policy.acceptable_states:
            return presence, pinned_id, row, AdbTransportPreparationStatus.SATISFIED
        if row.state in policy.blocked_states:
            return presence, pinned_id, row, AdbTransportPreparationStatus.BLOCKED
        return presence, pinned_id, row, None

    def _connect(self) -> NativeAttemptResult:
        address = self.binding_configuration.connect_address
        assert address is not None
        command = AdbTcpConnect(address)
        attempt = self._connector.connect(command)
        self._bus.publish(AdbTransportCommandCompleted(command, attempt))
        return attempt

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

    def _complete(
        self,
        operation: AdbTransportPreparation,
        policy: AdbTransportPreparationPolicy,
        session_id: AdbObservationSessionId,
        status: AdbTransportPreparationStatus,
        attempts: list[NativeAttemptResult],
        presence: AdbTransportPresenceSatisfaction | None,
        final_snapshot: AdbDevicesSnapshot | None,
        final_row: AdbTrackedDevice | None,
        pinned_id: AdbTransportId | None,
        diagnostic: str | None,
        *,
        already_satisfied: bool = False,
    ) -> AdbTransportPreparationResult:
        satisfaction = None
        if status is AdbTransportPreparationStatus.SATISFIED:
            satisfaction = (
                AdbTransportPreparationSatisfaction.ALREADY_SATISFIED
                if already_satisfied
                else AdbTransportPreparationSatisfaction.ACHIEVED
            )
        result = AdbTransportPreparationResult(
            operation=operation,
            policy=policy,
            status=status,
            satisfaction=satisfaction,
            presence_satisfaction=presence,
            observation_session_id=session_id,
            attempts=tuple(attempts),
            final_snapshot=final_snapshot,
            final_row=final_row,
            pinned_transport_id=pinned_id,
            diagnostic=diagnostic,
        )
        self._bus.publish(AdbTransportPreparationCompleted(result))
        return result


__all__ = ["AdbTransportPreparationOrchestrator"]
