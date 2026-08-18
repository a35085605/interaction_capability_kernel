# Operations and composition boundaries

## Ownership and CQS

Package placement follows domain or capability ownership. Command-Query Separation (CQS)
classifies **atomic operations** inside those owners:

- a **query** acquires or derives facts without intentionally changing the external
  environment;
- a **command** requests an external state change.

CQS does not determine package ownership. A platform domain may also own orchestration that
composes its models, queries, commands, and explicit policy while preserving the underlying
facts and native attempts.

## Atomic native queries

Native domains expose atomic query contracts keyed by domain-owned identities or bindings:

```text
DesktopInspector.inspect()                                             -> DesktopState
WindowInspector.inspect(WindowId)                                      -> WindowState | None
adb.server AdbServerStatusReader.read(endpoint)                        -> AdbServerStatus
adb.transport.devices AdbDevicesSnapshotReader.read(endpoint)        -> AdbDevicesSnapshot
adb.transport.devices AdbTrackedDeviceLookup.find(endpoint, selector)
                                                                       -> AdbTrackedDevice | None
adb.transport AdbTransportFeaturesReader.read(endpoint, selector)      -> AdbTransportFeatures
android.adb AdbBootStateInspector.inspect(endpoint, selector)          -> AndroidBootState
android.adb AdbBuildInfoInspector.inspect(endpoint, selector)          -> AndroidBuildInfo
android.adb AdbCurrentUserInspector.inspect(endpoint, selector)        -> AndroidUserId
android.adb AdbUsersInspector.inspect(endpoint, selector)              -> AndroidUsersSnapshot
android.adb AdbDisplaysInspector.inspect(endpoint, selector)           -> AndroidDisplaysSnapshot
android.adb AdbDisplayInspector.inspect(endpoint, selector, display)
                                                                       -> AndroidDisplayState | None
android.adb AdbPhysicalDisplaysInspector.inspect(endpoint, selector)
                                                                       -> AndroidPhysicalDisplaysSnapshot
android.adb AdbUserStateInspector.inspect(endpoint, selector, user)
                                                                       -> AndroidUserState | None
android.adb AdbPackageStateInspector.inspect(endpoint, selector, user, package)
                                                                       -> AndroidPackageState
android.adb AdbLauncherActivityInspector.inspect(endpoint, selector, user, package)
                                                                       -> AndroidComponentName | None
android.adb AdbResumedActivitiesInspector.inspect(endpoint, selector)
                                                                       -> AndroidResumedActivitiesSnapshot
android.adb AdbWindowsInspector.inspect(endpoint, selector)            -> AndroidWindowsSnapshot
android.adb AdbWindowInspector.inspect(endpoint, selector, window)
                                                                       -> AndroidWindowState | None
android.adb AdbDisplayOcclusionsInspector.inspect(endpoint, selector, display)
                                                                       -> AndroidDisplayOcclusionsSnapshot | None
android.adb AdbPowerStateInspector.inspect(endpoint, selector)         -> AndroidPowerState
android.adb AdbKeyguardStateInspector.inspect(endpoint, selector)
                                                                       -> AndroidKeyguardState
```

These contracts return domain-owned facts. `AdbDevicesSnapshotReader` acquires the complete
ADB server transport inventory, while `AdbTrackedDeviceLookup` derives singular selection from
a fresh inventory snapshot. Android framework facts remain Android-owned even when ADB is the
access mechanism under `android.adb`. Logical `AndroidDisplayId` and physical
`AndroidPhysicalDisplayId` remain distinct native identities.

Long-lived ADB tracker sources expose complete transport-inventory snapshots from the ADB
service. Connection loss ends the observation session; reconnection, retry, and snapshot
projection remain explicit behavior outside the source.

## Atomic commands

Platform domains own native state mutations:

```text
windows.command          WindowActivation / Move / Resize / ...
adb.server.lifecycle     AdbServerStart / AdbServerStop
adb.pairing.command      pair
adb.transport.connection connect / disconnect / reconnect
android.command          AndroidActivityLaunch / AndroidPackageForceStop
```

One command-adapter call represents at most one native attempt. `NativeAttemptResult` reports
the strongest native completion boundary reached by that attempt. An atomic adapter does not
hide retry loops, fallback to another mechanism, sequences of native commands, or
application-level success judgments.

Wireless pairing is owned separately from transports because it establishes the host-device
authentication/trust relationship against a pairing endpoint; it does not require an existing
`AdbTransportSelector`. Transport connection commands remain under `adb.transport`.

Platform-neutral pointer, keyboard, text, navigation, and touch interactions are separate
contracts under `execution`; platform-native operations stay with the domain that owns their
native nouns and semantics.

## Domain-local orchestration

A platform domain may compose its own models, atomic queries, atomic commands, and explicit
policy when the resulting semantics still belong to that domain:

```text
ADB-domain fact/query
       │
       ▼
 domain orchestration
   ┌───┴────┐
   ▼        ▼
 query    command
   │        │
   └───┬────┘
       ▼
 fresh ADB-domain evidence
```

`adb.server.lifecycle` owns server-availability composition such as
`AdbServerEnsureAvailable` and `AdbServerEnsureUnavailable`, including the bounded
`AdbServerEnsureOrchestrator`. Long-lived transport-observation lifecycle supervision lives
under `adb.supervision` rather than under the server noun slice. `adb.transport.orchestration`
owns transport preparation/recovery requests keyed by `AdbServerEndpoint` and
`AdbDeviceSerial`. When orchestration performs multiple native attempts, its result preserves
those attempts individually rather than collapsing them into one `NativeAttemptResult`.

Transport preparation keeps **responsibilities separate while keeping one episode**:

```text
ADB endpoint + serial
          │
          ▼
 serial resolution
 ABSENT / RESOLVED / AMBIGUOUS
          │
          ▼
     presence gate
 matching row exists; state is not judged here
          │
          ▼
      state gate
 explicit acceptable / blocked state policy
          │
          ▼
AdbTransportPreparationResult
```

The episode uses one authoritative deadline and one active transport-inventory observation
generation. It subscribes before its fresh initial inventory read so updates that occur during
the probe or atomic connect attempt are not lost between separate orchestration phases. Each
snapshot re-resolves the configured serial from fresh inventory. A serial-selected preparation
therefore follows the current unique row for that serial even when its server-local
`transport_id` changes between snapshots; a transient absence remains a waiting condition until
the deadline. Runtime transport IDs remain available for callers that explicitly require exact
`AdbTransportById` selection. A newer observation generation still terminates the episode
because it replaces the evidence-stream baseline.

Presence is evidence-driven. A failed atomic `AdbTcpConnect` attempt does not by itself make
the presence gate fail if fresh inventory evidence later resolves the configured serial. The
attempt remains in the preparation result, while satisfaction is determined from the observed
condition. Readiness is separately policy-driven; `DEVICE` is not a universal transport
success state, and unknown future AOSP state values remain non-satisfying unless a policy
explicitly accepts them.

## External composition

Cross-domain decisions are consumer-owned:

```text
platform facts / domain orchestration / capture / temporal facts
                              │
                              ▼
                    external composition
                  ┌───────────┼───────────┐
                  ▼           ▼           ▼
               mapping   platform cmd   execution
                  │           │           │
                  └───────────┴─────┬─────┘
                                    ▼
                            fresh query / capture
```

The kernel supplies domain facts, interaction capabilities, geometry, and same-domain
orchestration. A consuming coordinator, FSM, script, or agent decides native association,
backend selection, retry policy, evidence applicability, and application-effect semantics.
Application-level success is established from fresh evidence rather than inferred from a
native-attempt result.

## Temporal and scheduling

`temporal` reports wall-clock and monotonic time. Wall-clock values support calendar and
deadline semantics; monotonic values support elapsed-time calculations that must survive
wall-clock adjustments.

`scheduling` registers and cancels data-event delivery. A scheduler delivers data events to
external orchestration or an event queue; it does not invoke platform commands or execution
commands on its own.
