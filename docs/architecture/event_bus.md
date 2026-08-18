# Event bus and domain supervisors

`eventing` provides infrastructure-neutral publication/subscription contracts plus an
in-process FIFO adapter. Event payloads remain owned by the domain or capability that defines
their semantics; the bus owns delivery only.

```text
producer                         event bus                         consumer
   │                                │                                │
   ├── immutable domain signal ────►│── ordered type subscription ──►│
   │                                │                                │
   │                                │                     supervisor / projector
   │                                │                                │
   │◄──────────── new signals ──────┴────────────────────────────────┘
```

Cross-domain availability, backend selection, native retry, and application-effect semantics
remain outside `eventing`. A domain-local supervisor may consume signals and invoke same-domain
queries, commands, orchestration, and scheduling policy.

## In-process adapter

`InMemoryEventBus` serializes handler execution and drains one FIFO queue. Re-entrant and
concurrent publications are appended behind the current event, so handlers do not recursively
re-enter the delivery stack. Subscribers are invoked in registration order. Handler failures are
collected while later subscribers and queued events continue to receive delivery; the active
dispatcher receives an `EventDispatchError` after the queue is drained.

A handler that starts bounded orchestration which itself waits for later events from this bus must
not block the active dispatch stack. A domain supervisor may hand such work to its own worker and
return from the handler; the worker still consumes immutable lifecycle evidence through normal bus
subscriptions. The event bus remains delivery infrastructure and does not own that work.

This adapter is intended for one-process runtimes. Durable queues, distributed delivery,
persistence/replay, and cross-process backpressure remain external extensions.

## Scheduling boundary

`ThreadingTemporalScheduler` is a concrete in-process implementation of `TemporalScheduler`.
Timers publish their configured data event through an `EventPublisher`. Domain supervisors decide
what a due event means and which command, query, or orchestration operation to execute.

## ADB transport-inventory observation supervision

ADB server availability and transport-inventory observation are separate ADB-domain conditions.
`AdbServerEnsureOrchestrator` owns the bounded server condition-establishment path:

```text
fresh server probe
        │
        ├── desired state already observed ──► SATISFIED
        │
        └── otherwise
                 │
                 ▼
          at most one atomic
           start/stop attempt
                 │
                 ▼
        fresh verification probes
                 │
                 ▼
              result
```

`AdbDevicesObservationEstablishmentOrchestrator` composes that server sub-episode
with one new `track-devices` observation generation. It is itself bounded by one authoritative
establishment deadline and owns no retry/backoff state. A call to
`AdbDevicesObservationController.start()` only requests a new generation;
establishment is satisfied only after the matching `AdbDevicesObservationStarted`
signal proves that the tracker entered stream mode. A matching failure or stop before that
evidence terminates the episode as unsatisfied.

```text
fresh server probe
        │
        ├── INDETERMINATE ───────────────────► FAILED
        │
        ├── UNAVAILABLE ──► ensure available
        │                         │
        └── AVAILABLE ◄───────────┘
                  │
                  ▼
        start observation generation
                  │
                  ▼
       wait for matching lifecycle evidence
          ┌───────┼─────────┐
          │       │         │
       Started   Failed   deadline
          │       │         │
          ▼       ▼         ▼
      SATISFIED FAILED   TIMED_OUT
```

`AdbDevicesObservationSupervisor` under `adb.supervision` is the long-lived lifecycle
owner around those bounded establishment episodes. Startup initialization and runtime
server-connection re-establishment use the same establishment path. The supervisor retains one
`AdbDevicesObservationEstablishmentCycleId` across retry attempts and owns
retry/backoff, jitter, attempt budgets, current-generation filtering, and close behavior. It
clears the cycle only after an establishment episode is actually satisfied, so a server that
remains probeable while new tracker generations repeatedly fail to establish cannot reset the
retry budget merely by allocating another generation id.

Runtime `AdbDevicesObservationFailed(SERVER_CONNECTION)` signals are handled outside
the active `InMemoryEventBus` dispatch stack before waiting for establishment evidence. Scheduled
`adb.supervision.signal.AdbDevicesObservationEstablishmentRetryDue` signals follow the
same rule. `SERVICE` and `PROTOCOL` failures do not start the runtime re-establishment cycle.
Server ensure remains a sub-step of an establishment episode rather than the identity of the
long-lived supervision cycle.

`AdbObservationSessionId` combines the `AdbServerEndpoint` with a monotonically increasing
generation. `AdbDevicesObservation*` lifecycle signals and
`AdbDevicesSnapshotObserved` carry this identity, allowing the supervisor and bounded
episodes to ignore evidence for another generation. A newly established session is also a new
snapshot baseline; consumers must not diff snapshots across session generations.

Every server probe, native server attempt, and terminal ensure result remains observable through
the immutable ADB server signal vocabulary. Observation establishment additionally preserves the
new generation identity and typed establishment failure in its returned episode result.
