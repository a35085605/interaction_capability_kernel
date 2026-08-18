# ADB server endpoint provisioning

ADB server provisioning owns only allocation and reservation of native `AdbServerEndpoint`
values. It does not own caller identity. A consumer that uses a logical `server_id` keeps the
`server_id -> AdbServerEndpoint` association in its composition or adapter layer, resolves that
binding before entering the ADB domain, and passes only the endpoint into ADB contracts.

```text
caller / composition
  │
  │ caller-owned server_id
  ▼
server binding adapter
  │
  │ resolve or create binding
  ▼
AdbServerEndpoint
  │
  ├── optional endpoint provisioner
  │       └── reserve native endpoint
  │
  ▼
ADB operation plane
query / command / observation / orchestration
```

## Ownership boundary

The ADB domain knows the native smart-socket endpoint. It does not define a caller-owned server
identity and does not persist a mapping from logical ids to endpoints. This keeps native ADB
evidence scoped to native values and makes rebinding policy an explicit concern of the consumer
that owns the logical identity.

If a caller changes the endpoint associated with one of its logical ids, that is a caller-side
binding replacement. Existing ADB observation generations, preparation episodes, and retry
cycles remain scoped to the endpoint with which they were created; the caller decides when to
close them and construct new endpoint-scoped components.

## Endpoint reservation

`InMemoryAdbServerProvisioner` reserves distinct `AdbServerEndpoint` values within one
process-local provisioning scope. `provision()` accepts an optional explicit endpoint; when no
endpoint is supplied, `SequentialLocalAdbServerEndpointAllocator` selects the first unreserved
`localhost` port beginning at 5037.

The provisioner deliberately does not probe operating-system socket availability. Reservation
establishes only endpoint uniqueness in the provisioning scope. Native server availability is
established separately through `adb.server.status` and `adb.server.lifecycle`.

An explicit endpoint that is already reserved is rejected with
`AdbServerEndpointConflictError`. Endpoint exhaustion is reported as
`AdbServerEndpointExhaustedError`. The provisioner has no `resolve(server_id)` or rebind API
because caller identity is outside this domain.

## Observation identity

`AdbObservationSessionId` is endpoint-scoped: it contains the `AdbServerEndpoint` plus a
monotonically increasing generation. The generation identifies replacement of the observation
baseline for that endpoint; it is not a caller-side binding epoch.
