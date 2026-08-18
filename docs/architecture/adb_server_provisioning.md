# ADB server provisioning

ADB server provisioning owns the process-local association between a caller-owned
`AdbServerId` and the `AdbServerEndpoint` used by ADB-native readers, commands, observation,
and same-domain orchestration.

The provisioning model deliberately keeps the binding immutable for its runtime lifetime.
Provisioning may choose an endpoint automatically or accept an explicit endpoint, but it does
not support runtime rebinding.

```text
caller
  │
  │ server_id + optional endpoint
  ▼
ADB server provisioner
  │
  ├── endpoint omitted ──► allocator
  │
  └── endpoint supplied ─► validate ownership
              │
              ▼
    AdbServerConfiguration
       server_id + endpoint
              │
              ▼
       ADB operation plane
```

## Invariants

Within one authoritative provisioner:

- one `AdbServerId` has at most one active `AdbServerConfiguration`;
- one exact `AdbServerEndpoint` value is owned by at most one `AdbServerId`;
- provisioning an existing id with no endpoint reuses the existing binding;
- provisioning an existing id with the same endpoint also reuses the existing binding;
- provisioning an existing id with a different endpoint is rejected;
- provisioning a new id with an endpoint already owned by another id is rejected; and
- no `rebind` operation exists in this model.

The endpoint uniqueness rule compares `AdbServerEndpoint` values. Callers that supply host
aliases which resolve to the same native socket remain responsible for avoiding that external
aliasing.

## Automatic allocation

`SequentialLocalAdbServerEndpointAllocator` allocates `localhost` endpoints beginning at port
5037 and skips endpoint values already reserved by the provisioner. The allocator intentionally
does not probe operating-system socket availability and does not silently choose another port
because a native start attempt later fails. Allocation establishes configuration identity;
server availability remains evidence produced by `adb.server.status` and
`adb.server.lifecycle`.

A different allocation policy can implement `AdbServerEndpointAllocator` and be injected into
`InMemoryAdbServerProvisioner`.

## Explicit endpoints

A provisioning caller may supply an `AdbServerEndpoint` explicitly. Once accepted, that
endpoint is part of the immutable `AdbServerConfiguration` for the lifetime of the provisioner.
Ordinary ADB operations continue to consume the resulting configuration or its endpoint; they
do not decide how that endpoint was selected.

## Runtime rebinding

Runtime endpoint replacement is intentionally out of scope. Supporting it would introduce a
separate server-binding incarnation lifecycle and would require fencing long-lived observation,
preparation, supervision, scheduled retries, and other evidence against binding replacement.
`AdbObservationSessionId.generation` remains dedicated to observation-baseline replacement and
does not double as a server-binding epoch.
