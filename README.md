# Interaction capability kernel

This repository provides platform-neutral interaction capabilities plus platform-domain
contracts and adapters for interacting with an external environment. It is an interaction
kernel, not an agent runtime or a cross-domain operational model.

Package placement follows **ownership first**. Platform domains own their native models,
atomic queries, atomic commands, and domain-local orchestration. Interaction capabilities
such as `capture` and `execution` own platform-neutral interaction contracts. Command-Query
Separation (CQS) classifies atomic operations inside those owners: queries acquire facts
without intentionally changing the environment; commands request external state changes.

Package names do not have to mirror the CQS classification. Once an owner is established,
semantic noun slices may be the canonical namespace while CQS remains an operation-level
constraint inside the slice. For example, ADB server status lives under `adb.server.status`,
server lifecycle under `adb.server.lifecycle`, and transport connection under
`adb.transport.connection`.

```text
Platform/native domains                     Interaction capabilities
windows / adb / android                     capture / execution
        │                                           │
        ├── model                                    │
        ├── atomic query                             │
        ├── atomic command                           │
        └── domain-local orchestration               │
                 │                                   │
                 └──────────┬────────────────────────┘
                            ▼
                 external cross-domain composition
                 coordinator / FSM / script / agent
```

The kernel does not provide a cross-domain coordinator. A consuming coordinator may combine
facts and capabilities across domains, but backend selection, retry policy, evidence
applicability, and application-effect semantics remain outside the kernel.

## Core rules

- Ownership determines package placement; CQS classifies atomic operations inside an owner.
- Native read/query contracts are atomic and use identities or bindings owned by their own domain.
- Native commands are atomic: one adapter call represents at most one native attempt.
- A platform domain may provide orchestration that composes its own models, queries, commands,
  and explicit policy while preserving underlying evidence and attempts.
- The kernel does not provide cross-domain coordinators or aggregate target-runtime state.
- `capture` and `execution` are peer interaction capabilities, not platform administration
  layers.
- Capture is read-only and reports capture-owned acquisition outcomes rather than
  cross-domain availability policy.
- `InteractionTargetId` is only an opaque logical identity; native association is external
  composition.
- Historical application-raster geometry is mapped into a fresh platform presentation before
  execution when a consumer decides the evidence still applies.
- Native-attempt success reports only the native completion boundary that was reached;
  application-level effects require fresh evidence.
- Geometry owns math; native domains own the meaning of their surfaces and coordinates.

## Capability map

The repository provides reusable contracts and data models for:

- minimal interaction-target identity;
- visual capture and typed acquisition failure;
- platform-neutral pointer, keyboard, text, navigation, and touch execution contracts;
- atomic Windows desktop-global and Window inspectors plus Window atomic commands;
- AOSP-aligned ADB server status, transport-inventory snapshots, selected-transport features,
  server/pairing/transport atomic commands, domain-local orchestration, long-lived server
  condition supervision, and event-driven transport-inventory observation supervision;
- Android build, boot, current-user/profile, package/activity, WindowManager geometry/insets,
  and logical/physical-display facts reached through ADB;
- Android-native activity-launch and package-force-stop atomic commands;
- deterministic Android physical-display capture through ADB screencap;
- Android display-local tap, long-press, swipe, drag-and-drop, key, key-combination, limited
  portable text, and Back execution adapters;
- wall-clock and monotonic time;
- data-event scheduling and in-process event-bus delivery;
- application presentations, correspondence, and durable application rasters; and
- geometry, raster, crop, resize, and transform math.

Atomic native queries are owned by their native domains. ADB host-side read contracts name the
fact they return; `AdbTrackedDeviceLookup` derives one observed row from a fresh complete
inventory snapshot:

```python
from windows.query import DesktopInspector, WindowInspector
from adb.server.status import AdbServerStatusReader
from adb.transport.devices.query import (
    AdbDevicesSnapshotReader,
    AdbTrackedDeviceLookup,
)
from adb.transport.query import AdbTransportFeaturesReader
from android.adb.query import (
    AdbBootStateInspector,
    AdbBuildInfoInspector,
    AdbCurrentUserInspector,
    AdbDisplayInspector,
    AdbDisplayOcclusionsInspector,
    AdbDisplaysInspector,
    AdbKeyguardStateInspector,
    AdbLauncherActivityInspector,
    AdbPackageStateInspector,
    AdbPhysicalDisplaysInspector,
    AdbPowerStateInspector,
    AdbResumedActivitiesInspector,
    AdbUsersInspector,
    AdbUserStateInspector,
    AdbWindowInspector,
    AdbWindowsInspector,
)
```

Atomic platform commands stay beside the noun slice that owns their native semantics:

```python
from windows.command import WindowActivation, WindowMove
from adb.server.lifecycle import AdbServerStart, AdbServerStop
from adb.pairing.command import AdbWirelessPair
from adb.transport.connection import AdbTcpConnect, AdbTransportReconnect
from android.command import AndroidActivityLaunch, AndroidPackageForceStop
```

Domain-local orchestration remains distinct from atomic commands even when both share a
semantic noun namespace:

```python
from adb.server.lifecycle import (
    AdbServerEnsureAvailable,
    AdbServerEnsureOrchestrator,
    AdbServerEnsurePolicy,
    AdbServerEnsureResult,
)
from adb.supervision import AdbDevicesObservationSupervisor, AdbServerSupervisor
from adb.transport.binding import AdbTransportBindingConfiguration
from adb.transport.orchestration import (
    AdbTransportPreparation,
    AdbTransportPreparationPolicy,
    AdbTransportPreparationResult,
    AdbTransportRecovery,
)
from adb.transport.preparation import AdbTransportPreparationOrchestrator
```

Queries/readers and commands do not accept a cross-domain runtime target and do not aggregate
facts from other native domains. Host-side ADB ownership is centered on `adb.server`, `adb.pairing`, and
`adb.transport`; server status is under `adb.server.status`, server lifecycle under
`adb.server.lifecycle`, transport connection mutations under `adb.transport.connection`, the
server-observed transport inventory under `adb.transport.devices`, and its long-lived
`track-devices` lifecycle under `adb.transport.observation`. ADB-backed Android framework
queries live under `android.adb`.

## ADB host facts and configuration

The low-level ADB host model uses AOSP host protocol vocabulary:

```text
AdbServerStatus       adb_host.proto.AdbServerStatus payload
AdbDevicesSnapshot    adb_host.proto.Devices transport-inventory snapshot
AdbTrackedDevice      adb_host.proto.Device observed row
AdbConnectionState    adb_host.proto.ConnectionState values
AdbConnectionType     adb_host.proto.ConnectionType values
```

`AdbTrackedDevice` is one wire-aligned observation row for a server-tracked ADB transport. A
non-zero `AdbTrackedDevice.transport_id` is the server-local native runtime transport identity;
the protobuf default zero means that runtime identity is unavailable in the row. The observation
layer publishes complete inventory snapshots. Different non-zero transport IDs denote different
runtime transport instances.

`AdbServerEndpoint` is the ADB-domain identity of one smart-socket server endpoint and is the
server value consumed by host-side ADB queries, commands, observation, and same-domain
orchestration. External composition owns caller logical server ids and their association with
`AdbServerEndpoint`. `AdbDeviceSerial` is the persistent native selection key for configured ADB
transports. `AdbTransportBySerial` passes that serial directly to native ADB serial-selection
mechanisms; it does not require a transport-inventory snapshot or conversion to
`AdbTransportById`. `AdbTransportId` is a server-local runtime identity derived from fresh
inventory evidence; it is not a durable configuration key. `AdbTransportFeatures` is a
selected-transport fact with an open native feature vocabulary. Android runtime facts remain
Android-owned and are acquired through `android.adb`.

`AdbTransportBindingConfiguration` associates one ADB server endpoint with an `AdbDeviceSerial`
and an optional TCP connect address. The serial is deliberately independent from the connect
address; preparation does not assume that the string passed to `adb connect` must later be the
tracker serial. Preparation uses fresh inventory only to locate the row for that serial and
evaluate presence/state evidence. That lookup does not change native selection to a runtime
`transport_id`. Runtime `transport_id` values remain fresh inventory facts rather than binding
configuration or implicit preparation continuity state.

Concrete ADB-backed adapters share a private smart-socket service client. Public queries,
capture backends, platform commands, and execution adapters expose typed contracts owned by
their domains or capabilities.

`adb.server.status` owns server-status facts and the atomic status reader.
`adb.server.lifecycle` owns atomic `AdbServerStart` / `AdbServerStop` commands plus the bounded
server-availability ensure vocabulary and executor. Atomic server commands still represent one
native attempt. `adb.pairing.command` owns one-attempt wireless pairing/trust establishment.
`adb.transport.connection` owns one-attempt transport connection mutations while
`adb.transport.orchestration` owns preparation/recovery composition vocabulary. Domain
orchestration preserves the evidence for each native attempt it performs.

Transport preparation is one bounded episode with two distinct gates. The **presence gate**
locates the configured serial in complete inventory snapshots and is satisfied by a matching
row regardless of its `AdbConnectionState`. The **state gate** then applies an explicit
`AdbTransportPreparationPolicy` to the same episode and observation generation. Each fresh
snapshot locates the current row for the configured serial so preparation can evaluate fresh
presence/state evidence. This inventory lookup is not a selector translation: serial-selected
queries and commands still select directly by serial. Exact runtime-transport continuity remains
available only when a caller explicitly selects with `AdbTransportById`. Atomic `adb connect`
attempt evidence is preserved, but fresh inventory evidence determines whether preparation is
satisfied.

`SubprocessAdbPairing` and `SubprocessAdbTransport` are each bound directly to an
`AdbServerEndpoint` and pass that endpoint through `-H` / `-P` to their CLI commands.
Pairing establishes the host-device wireless-debugging trust relationship; transport commands
manage transport connection state separately.

## Event delivery and ADB server / observation supervision

`eventing` owns publication/subscription infrastructure, not domain behavior.
`InMemoryEventBus` provides ordered in-process FIFO delivery. Domain signals remain immutable
payloads owned by their domain; supervisors decide what those signals mean.

ADB server availability and transport-inventory observation are supervised as separate long-lived
conditions. `AdbServerEnsureOrchestrator` remains the bounded probe / one atomic server command /
fresh verification executor. `AdbServerSupervisor` adds desired-running intent, an automatic
recovery gate, retry/backoff, stale recovery-cycle fencing, and serialization of managed server
start/stop mutations. It does not hide a liveness source: `reconcile()` is the entry point for fresh
reconciliation when another runtime component has reason to check the server condition.

`AdbDevicesObserver` establishes `track-devices` stream mode before emitting
`AdbDevicesObservationStarted`, emits complete snapshots through
`AdbDevicesSnapshotObserved`, and attaches an
`AdbObservationSessionId` containing the ADB server endpoint plus a monotonically increasing
generation. Its `active_session_id` identifies only the allocated non-terminal generation and
is cleared before terminal `AdbDevicesObservationStopped` or `AdbDevicesObservationFailed`
evidence is published. A new generation establishes a new observation baseline; observation
termination does not imply that transports disappeared.

`AdbDevicesObservationEstablishmentOrchestrator` now owns only one bounded establishment of a
`track-devices` observation generation. It does not probe, start, or stop the ADB server;
satisfaction requires matching `AdbDevicesObservationStarted` evidence.
`AdbDevicesObservationSupervisor` owns the long-lived observation establishment cycle across
retry attempts and generations, consumes current-generation server-connection failures, and
schedules `AdbDevicesObservationEstablishmentRetryDue` data events with bounded exponential
backoff and optional jitter. A server-connection failure is therefore observation evidence, not
authority to mutate server desired state.

`adb.managed` also exposes the intentionally unimplemented `AdbManagedRuntime` /
`RegisteredTransport` public skeleton. That scaffold reserves the future composition boundary for
server desired state, observation demand, and registered transport recovery without moving those
policies into atomic commands or bounded observation establishment.

## Presentation correspondence and execution geometry

`ApplicationPresentationCorrespondenceAnchor` is a consumer assertion that equally anchored
full presentations may be related by an invertible axis-aligned transform.
`ApplicationPresentationMapping` derives that transform from their rectangles.

A historical capture can be reduced to a durable, zero-based
`ApplicationPresentationRaster`. When external composition decides that historical evidence
still applies, raster-local geometry can be mapped into a fresh platform-owned presentation:

```text
historical application-raster point
        │ ApplicationPresentationMapping
        ▼
fresh application point
        │
        ├── local-coordinate execution backend ──► native attempt
        │
        └── root-coordinate execution backend ───► LocalPlacement ──► native attempt
```

See [`presentation_geometry.md`](docs/architecture/presentation_geometry.md).

## Platform commands, execution, and verification

Platform commands mutate platform-native state such as Window activation, ADB server
lifecycle, transport reconnect, Android activity launch, or package force-stop. `execution`
is separate: it owns platform-neutral interaction command contracts such as pointer, key,
text, navigation, and touch semantics. `capture` is a peer interaction capability for
read-only visual acquisition.

A successful native attempt is not application-level success. Consumers query or capture
again when they need to verify the intended effect.

## External extensions

Extensions live outside this repository and depend on public kernel contracts. The core does
not vendor or auto-discover them. Detector/perception implementations are one example: they
may consume capture, application-raster, imaging, and geometry contracts and return their own
findings and provenance models.

Extensions that introduce native mechanisms should model their own platform nouns,
identities/bindings, atomic query contracts, atomic commands, domain-local orchestration,
spatial surfaces, and execution adapters, then wire them explicitly through consumer
composition.

See [`extensions.md`](docs/architecture/extensions.md).

## Out of scope

The kernel does not provide planners, goals, application workflows, cross-domain retry
policy, world models, memory, evidence-fusion policy, application-effect semantics, or
application-specific automation logic.

## Architecture guide

- [`terminology.md`](docs/architecture/terminology.md) — canonical vocabulary.
- [`operations.md`](docs/architecture/operations.md) — ownership, atomic CQS, domain-local
  orchestration, external composition, temporal facts, and scheduling.
- [`native_entities_and_surfaces.md`](docs/architecture/native_entities_and_surfaces.md)
  — native state, transport bindings, query contracts, and platform-owned surfaces.
- [`presentation_geometry.md`](docs/architecture/presentation_geometry.md) — application
  presentations, historical evidence, mapping, native placement, and layout scaling.
- [`capture_backends.md`](docs/architecture/capture_backends.md) — read-only capture,
  typed unavailability, and materialization.
- [`execution_capabilities.md`](docs/architecture/execution_capabilities.md) — platform-neutral
  interaction execution and native-attempt boundaries.
- [`event_bus.md`](docs/architecture/event_bus.md) — event delivery, scheduling, and ADB
  server / transport-inventory supervision.
- [`extensions.md`](docs/architecture/extensions.md) — external capability ownership.
