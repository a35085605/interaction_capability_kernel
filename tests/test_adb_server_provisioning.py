from __future__ import annotations

import unittest

from adb.configuration import AdbServerId
from adb.server.endpoint import AdbServerEndpoint
from adb.server.provisioning import (
    AdbServerBindingConflictError,
    AdbServerEndpointConflictError,
    AdbServerEndpointExhaustedError,
    InMemoryAdbServerProvisioner,
    SequentialLocalAdbServerEndpointAllocator,
)


class AdbServerProvisioningTests(unittest.TestCase):
    def test_auto_provisioning_allocates_distinct_local_endpoints(self) -> None:
        provisioner = InMemoryAdbServerProvisioner()

        first = provisioner.provision(AdbServerId("first"))
        second = provisioner.provision(AdbServerId("second"))

        self.assertEqual(first.endpoint, AdbServerEndpoint("localhost", 5037))
        self.assertEqual(second.endpoint, AdbServerEndpoint("localhost", 5038))
        self.assertNotEqual(first.endpoint, second.endpoint)

    def test_explicit_endpoint_is_preserved(self) -> None:
        provisioner = InMemoryAdbServerProvisioner()
        endpoint = AdbServerEndpoint("127.0.0.1", 5040)

        configuration = provisioner.provision(
            AdbServerId("explicit"),
            endpoint=endpoint,
        )

        self.assertEqual(configuration.endpoint, endpoint)
        self.assertIs(provisioner.resolve(configuration.server_id), configuration)

    def test_repeated_provision_reuses_existing_binding(self) -> None:
        provisioner = InMemoryAdbServerProvisioner()
        server_id = AdbServerId("stable")

        first = provisioner.provision(server_id)
        second = provisioner.provision(server_id)
        third = provisioner.provision(server_id, endpoint=first.endpoint)

        self.assertIs(second, first)
        self.assertIs(third, first)

    def test_existing_server_id_cannot_be_rebound_at_runtime(self) -> None:
        provisioner = InMemoryAdbServerProvisioner()
        server_id = AdbServerId("immutable")
        first = provisioner.provision(server_id, endpoint=AdbServerEndpoint("localhost", 5039))

        with self.assertRaises(AdbServerBindingConflictError):
            provisioner.provision(
                server_id,
                endpoint=AdbServerEndpoint("localhost", 5040),
            )

        self.assertIs(provisioner.resolve(server_id), first)

    def test_different_server_ids_cannot_share_one_endpoint(self) -> None:
        provisioner = InMemoryAdbServerProvisioner()
        endpoint = AdbServerEndpoint("localhost", 5041)
        provisioner.provision(AdbServerId("owner"), endpoint=endpoint)

        with self.assertRaises(AdbServerEndpointConflictError):
            provisioner.provision(AdbServerId("alias"), endpoint=endpoint)

    def test_auto_allocator_skips_explicitly_reserved_endpoint(self) -> None:
        provisioner = InMemoryAdbServerProvisioner()
        provisioner.provision(
            AdbServerId("explicit-default"),
            endpoint=AdbServerEndpoint("localhost", 5037),
        )

        automatic = provisioner.provision(AdbServerId("automatic"))

        self.assertEqual(automatic.endpoint, AdbServerEndpoint("localhost", 5038))

    def test_allocator_exhaustion_is_typed(self) -> None:
        provisioner = InMemoryAdbServerProvisioner(
            SequentialLocalAdbServerEndpointAllocator(first_port=65535)
        )
        provisioner.provision(AdbServerId("last"))

        with self.assertRaises(AdbServerEndpointExhaustedError):
            provisioner.provision(AdbServerId("overflow"))


if __name__ == "__main__":
    unittest.main()
