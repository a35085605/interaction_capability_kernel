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

## ADB server and transport-inventory observation supervision

ADB server availability and transport-inventory observation are separate ADB-domain conditions,
and each condition now has its own long-lived supervisor.

`AdbServerEnsureOrchestrator` still owns one bounded server condition-establishment episode:

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

`AdbServerSupervisor` owns the durable running intent around those bounded episodes:

```text
desired_running + recovery_enabled
              │
              ▼
        recovery_armed
              │
              ▼
      bounded ensure-available
          ┌───┴────┐
          │        │
      satisfied  unsatisfied
          │        │
          │        ▼
          │   retry/backoff cycle
          │        │
          └────────┴──► fresh bounded reconciliation
```

`recovery_armed` is derived from `desired_running and recovery_enabled`; it is not a separately
stored preference. The supervisor requires `recovery_enabled` to be supplied explicitly when a
running intent is started. Caller-facing defaults such as `auto_recovery=True`, and any preference
that should survive a stop/start boundary, belong to the managed runtime rather than the
supervisor.

The server supervisor owns retry/backoff, the recovery gate, recovery-cycle fencing, and
serialization of managed server start/stop mutations. Disabling recovery does not stop the server
or change `desired_running`. `stop()` invalidates running recovery, clears the current
`recovery_enabled` state, and then serializes a bounded ensure-unavailable episode after any
already-entered managed server mutation.

The supervisor intentionally does not invent a hidden liveness source. `reconcile()` lets the
future managed runtime request a fresh server reconciliation when explicit runtime evidence (for
example, another supervised condition losing its server connection) makes that useful. A later
runtime policy may add other monitoring without coupling it to `track-devices`.

`AdbDevicesObservationEstablishmentOrchestrator` is now only the bounded establishment of one
`track-devices` observation generation. It owns no server lifecycle or retry/backoff policy:

```text
start observation generation
          │
          ▼
 wait for matching lifecycle evidence
    ┌─────┼─────────┐
    │     │         │
 Started Failed   deadline
    │     │         │
    ▼     ▼         ▼
SATISFIED FAILED TIMED_OUT
```

A call to `AdbDevicesObservationController.start()` only requests a new generation; establishment
is satisfied only after matching `AdbDevicesObservationStarted` evidence proves that the tracker
entered stream mode. A matching failure or stop before that evidence terminates the episode as
unsatisfied. No observation establishment path probes, starts, or stops the ADB server.

`AdbDevicesObservationSupervisor` remains the long-lived owner around those bounded observation
episodes. It retains one `AdbDevicesObservationEstablishmentCycleId` across retry attempts and
owns retry/backoff, jitter, attempt budgets, current-generation filtering, and close behavior.
Runtime `AdbDevicesObservationFailed(SERVER_CONNECTION)` starts an observation re-establishment
cycle but does not grant authority to mutate server desired state. `SERVICE` and `PROTOCOL`
failures still do not start that automatic re-establishment cycle. Scheduled
`AdbDevicesObservationEstablishmentRetryDue` signals remain data events; the scheduler does not
own control side effects.

`AdbObservationSessionId` combines the `AdbServerEndpoint` with a monotonically increasing
generation. `AdbDevicesObservation*` lifecycle signals and
`AdbDevicesSnapshotObserved` carry this identity, allowing the supervisor and bounded
episodes to ignore evidence for another generation. A newly established session is also a new
snapshot baseline; consumers must not diff snapshots across session generations.

Every server probe, native server attempt, and terminal ensure result remains observable through
the immutable ADB server signal vocabulary. Observation establishment separately preserves the new
generation identity and typed observation failure in its returned episode result.

`adb.managed.AdbManagedRuntime` and `RegisteredTransport` are currently a public scaffold only;
their methods deliberately raise `NotImplementedError`. The scaffold marks the future coordination
boundary where caller-facing recovery defaults, liveness-source-to-reconcile policy, server desired
state, observation demand, and registered transport recovery can be composed without merging their
supervisor ownership.
