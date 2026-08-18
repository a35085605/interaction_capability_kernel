from __future__ import annotations

from threading import Lock
from typing import Protocol, runtime_checkable

from adb.configuration import AdbServerConfiguration, AdbServerId
from adb.server.endpoint import AdbServerEndpoint


class AdbServerProvisioningError(RuntimeError):
    """Base error for configured ADB server provisioning failures."""


class AdbServerBindingConflictError(AdbServerProvisioningError):
    """An existing server id was requested with a different endpoint."""


class AdbServerEndpointConflictError(AdbServerProvisioningError):
    """An endpoint is already owned by another configured server id."""


class AdbServerEndpointExhaustedError(AdbServerProvisioningError):
    """The endpoint allocator could not produce another unreserved endpoint."""


@runtime_checkable
class AdbServerEndpointAllocator(Protocol):
    """Allocate one endpoint not present in the supplied reservation set."""

    def allocate(
        self,
        reserved_endpoints: frozenset[AdbServerEndpoint],
    ) -> AdbServerEndpoint: ...


class SequentialLocalAdbServerEndpointAllocator:
    """Allocate registry-unique localhost endpoints from a monotonically increasing port range.

    This allocator deliberately does not probe operating-system socket availability. Provisioning
    owns logical endpoint uniqueness between configured ADB servers; native server availability is
    established later through the existing ADB server lifecycle/query contracts.
    """

    def __init__(self, host: str = "localhost", first_port: int = 5037) -> None:
        first = AdbServerEndpoint(host=host, port=first_port)
        self.host = first.host
        self.first_port = first.port

    def allocate(
        self,
        reserved_endpoints: frozenset[AdbServerEndpoint],
    ) -> AdbServerEndpoint:
        if not isinstance(reserved_endpoints, frozenset):
            raise TypeError("reserved_endpoints must be a frozenset")
        for endpoint in reserved_endpoints:
            if not isinstance(endpoint, AdbServerEndpoint):
                raise TypeError("reserved_endpoints must contain AdbServerEndpoint values")

        for port in range(self.first_port, 65536):
            candidate = AdbServerEndpoint(self.host, port)
            if candidate not in reserved_endpoints:
                return candidate
        raise AdbServerEndpointExhaustedError(
            f"no unreserved ADB server endpoint remains for host {self.host!r} "
            f"starting at port {self.first_port}"
        )


@runtime_checkable
class AdbServerProvisioner(Protocol):
    """Provision immutable server-id to endpoint bindings for one runtime."""

    def provision(
        self,
        server_id: AdbServerId,
        *,
        endpoint: AdbServerEndpoint | None = None,
    ) -> AdbServerConfiguration: ...

    def resolve(self, server_id: AdbServerId) -> AdbServerConfiguration | None: ...


class InMemoryAdbServerProvisioner:
    """Own immutable configured-server bindings for one process-local provisioning scope.

    A new server id may request an explicit endpoint or omit it to use the configured allocator.
    Re-provisioning the same id reuses its existing binding. Supplying a different endpoint for an
    already-bound id is rejected rather than silently rebinding it. Endpoints are exclusively owned
    by one server id within this provisioner.
    """

    def __init__(self, allocator: AdbServerEndpointAllocator | None = None) -> None:
        allocator = allocator or SequentialLocalAdbServerEndpointAllocator()
        if not callable(getattr(allocator, "allocate", None)):
            raise TypeError("allocator must provide allocate()")
        self._allocator = allocator
        self._by_server_id: dict[AdbServerId, AdbServerConfiguration] = {}
        self._by_endpoint: dict[AdbServerEndpoint, AdbServerId] = {}
        self._lock = Lock()

    def provision(
        self,
        server_id: AdbServerId,
        *,
        endpoint: AdbServerEndpoint | None = None,
    ) -> AdbServerConfiguration:
        if not isinstance(server_id, AdbServerId):
            raise TypeError("server_id must be AdbServerId")
        if endpoint is not None and not isinstance(endpoint, AdbServerEndpoint):
            raise TypeError("endpoint must be AdbServerEndpoint or None")

        with self._lock:
            existing = self._by_server_id.get(server_id)
            if existing is not None:
                if endpoint is None or endpoint == existing.endpoint:
                    return existing
                raise AdbServerBindingConflictError(
                    f"ADB server {server_id.value!r} is already bound to "
                    f"{existing.endpoint.host}:{existing.endpoint.port}; runtime rebinding to "
                    f"{endpoint.host}:{endpoint.port} is not supported"
                )

            selected = endpoint
            if selected is None:
                selected = self._allocator.allocate(frozenset(self._by_endpoint))
                if not isinstance(selected, AdbServerEndpoint):
                    raise TypeError("allocator.allocate() must return AdbServerEndpoint")

            owner = self._by_endpoint.get(selected)
            if owner is not None:
                raise AdbServerEndpointConflictError(
                    f"ADB server endpoint {selected.host}:{selected.port} is already bound to "
                    f"server {owner.value!r}"
                )

            configuration = AdbServerConfiguration(server_id=server_id, endpoint=selected)
            self._by_server_id[server_id] = configuration
            self._by_endpoint[selected] = server_id
            return configuration

    def resolve(self, server_id: AdbServerId) -> AdbServerConfiguration | None:
        if not isinstance(server_id, AdbServerId):
            raise TypeError("server_id must be AdbServerId")
        with self._lock:
            return self._by_server_id.get(server_id)


__all__ = [
    "AdbServerBindingConflictError",
    "AdbServerEndpointAllocator",
    "AdbServerEndpointConflictError",
    "AdbServerEndpointExhaustedError",
    "AdbServerProvisioner",
    "AdbServerProvisioningError",
    "InMemoryAdbServerProvisioner",
    "SequentialLocalAdbServerEndpointAllocator",
]
