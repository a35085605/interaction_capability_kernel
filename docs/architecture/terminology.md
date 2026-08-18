# Terminology

## Interaction target

`InteractionTargetId` is an opaque caller-known logical identity for the thing being
interacted with. The kernel does not attach runtime availability, native entities, control
mechanisms, or platform geometry to this identity.

## Platform domain

A platform domain owns native nouns and semantics for one platform or native subsystem, such
as Windows, ADB, or Android. A domain may own models, atomic queries, atomic commands,
spatial surfaces, adapters, and orchestration whose resulting semantics remain inside that
domain.

## Atomic query

An atomic query acquires or derives one domain-owned fact without intentionally changing the
external environment. Native inspectors use domain-owned identity/binding inputs and do not
perform cross-domain aggregation or environment preparation.

## Atomic command

An atomic command requests one external state change through one native mechanism. One
command-adapter call represents at most one native attempt. Waiting, retry, fallback, and
multi-step recovery are not hidden inside an atomic command.

## Domain-local orchestration

Domain-local orchestration composes models, atomic queries, atomic commands, and explicit
policy owned by one platform domain. It may span noun slices inside that domain; cross-domain
composition and application-effect judgments remain consumer-owned.

## Interaction capability

An interaction capability owns platform-neutral interaction semantics rather than
platform-native state. `capture` owns read-only visual acquisition; `execution` owns
platform-neutral input/touch interaction commands. They are peer capabilities.

## Native entity and binding

`windows` owns desktop-global and Window vocabulary. Host-side ADB facts use AOSP host
protocol vocabulary: `AdbServerStatus`, `AdbDevicesSnapshot`, `AdbTrackedDevice`,
`AdbConnectionState`, and `AdbConnectionType`. The current native transport identity is
`AdbTrackedDevice.transport_id`; `AdbTransportFeatures` is the open advertised feature set
for one selected transport. `AdbServerId` is a caller-owned configuration identity and is
intentionally separate from native ADB facts. `AdbDeviceSerial` is the persistent native key
used to identify configured transports across inventory observations; `AdbTransportId` remains
a server-local runtime identity derived from those observations. `AdbServerConfiguration` is
an immutable binding from one `AdbServerId` to the smart-socket `AdbServerEndpoint` used for
host queries, commands, and ADB-domain orchestration. `adb.server.provisioning` owns creation
of those runtime bindings: callers may omit the endpoint for allocator-selected provisioning
or request an explicit endpoint, but an existing server id cannot be rebound to another
endpoint within the same provisioner. Exact endpoint values are exclusively owned by one
server id within that provisioning scope. Android owns `AndroidUserId`, `AndroidPackageName`,
`AndroidComponentName`, logical `AndroidDisplayId`, and physical capture
`AndroidPhysicalDisplayId`. Logical and physical display IDs are never implicitly
interchangeable.

## Application presentation

`ApplicationPresentation` is a full rectangular application presentation in an external
composition context. `ApplicationPresentationCorrespondenceAnchor` declares which full
presentations may be mapped to each other by an invertible axis-aligned transform.
`ApplicationPresentationMapping` derives that geometry from equally anchored rectangles.

## Application presentation raster

`ApplicationPresentationRaster` is a durable zero-based raster for one anchored application
presentation. It retains source-capture identity and the correspondence anchor without
retaining historical capture placement.

## Native placement

`LocalPlacement` maps a subordinate native surface into its platform-owned root when a native
API requires root coordinates.

## Native attempt and application effect

`NativeAttemptResult` describes the strongest native completion boundary reached by one
actual attempt. Application-level success is a separate external judgment based on fresh
query or capture results.
