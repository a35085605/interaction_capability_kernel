from __future__ import annotations

import unittest

from adb.server.endpoint import AdbServerEndpoint
from adb.server.provisioning import (
    AdbServerEndpointConflictError,
    AdbServerEndpointExhaustedError,
    InMemoryAdbServerProvisioner,
    SequentialLocalAdbServerEndpointAllocator,
)


class AdbServerProvisioningTests(unittest.TestCase):
    def test_auto_provisioning_allocates_distinct_local_endpoints(self) -> None:
        provisioner = InMemoryAdbServerProvisioner()
        first = provisioner.provision()
        second = provisioner.provision()
        self.assertEqual(first, AdbServerEndpoint("localhost", 5037))
        self.assertEqual(second, AdbServerEndpoint("localhost", 5038))
        self.assertNotEqual(first, second)

    def test_explicit_endpoint_is_preserved(self) -> None:
        provisioner = InMemoryAdbServerProvisioner()
        endpoint = AdbServerEndpoint("127.0.0.1", 5040)
        self.assertIs(provisioner.provision(endpoint=endpoint), endpoint)

    def test_explicit_endpoint_cannot_be_reserved_twice(self) -> None:
        provisioner = InMemoryAdbServerProvisioner()
        endpoint = AdbServerEndpoint("localhost", 5041)
        provisioner.provision(endpoint=endpoint)
        with self.assertRaises(AdbServerEndpointConflictError):
            provisioner.provision(endpoint=endpoint)

    def test_auto_allocator_skips_explicitly_reserved_endpoint(self) -> None:
        provisioner = InMemoryAdbServerProvisioner()
        provisioner.provision(endpoint=AdbServerEndpoint("localhost", 5037))
        automatic = provisioner.provision()
        self.assertEqual(automatic, AdbServerEndpoint("localhost", 5038))

    def test_allocator_exhaustion_is_typed(self) -> None:
        provisioner = InMemoryAdbServerProvisioner(
            SequentialLocalAdbServerEndpointAllocator(first_port=65535)
        )
        provisioner.provision()
        with self.assertRaises(AdbServerEndpointExhaustedError):
            provisioner.provision()


if __name__ == "__main__":
    unittest.main()
