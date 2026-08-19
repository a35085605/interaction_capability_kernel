from __future__ import annotations

import unittest

from adb import AdbManagedRuntime, RegisteredTransport
from adb.server import AdbServerStatusReader as PublicServerStatusReader
from adb.server.lifecycle import AdbServerEnsurePolicy, AdbServerStart
from adb.server.lifecycle.adapters import SubprocessAdbServer
from adb.server.provisioning import (
    AdbServerProvisioner,
    InMemoryAdbServerProvisioner,
    SequentialLocalAdbServerEndpointAllocator,
)
from adb.server.status import AdbServerStatus, AdbServerStatusReader
from adb.supervision import (
    AdbDevicesObservationSupervisionPolicy,
    AdbDevicesObservationSupervisor,
    AdbServerSupervisionPolicy,
    AdbServerSupervisor,
)
from adb.transport.connection import AdbTcpConnect
from adb.transport.connection.adapters import SubprocessAdbTransport
from adb.transport.observation import AdbDevicesObservationEstablishmentPolicy


class AdbSemanticNamespaceTests(unittest.TestCase):
    def test_server_status_namespace_is_canonical(self) -> None:
        self.assertIs(AdbServerStatusReader, PublicServerStatusReader)
        self.assertEqual(AdbServerStatus.__module__, "adb.server.status.model")

    def test_server_lifecycle_namespace_is_canonical(self) -> None:
        self.assertEqual(AdbServerStart.__module__, "adb.server.lifecycle.command")
        self.assertEqual(SubprocessAdbServer.__module__, "adb.server.lifecycle.adapters")
        self.assertEqual(AdbServerEnsurePolicy.__module__, "adb.server.lifecycle.ensure")
        self.assertEqual(AdbServerEnsurePolicy(1.0, 0.1).timeout_seconds, 1.0)

    def test_server_provisioning_namespace_is_canonical(self) -> None:
        self.assertEqual(AdbServerProvisioner.__module__, "adb.server.provisioning")
        self.assertEqual(InMemoryAdbServerProvisioner.__module__, "adb.server.provisioning")
        self.assertEqual(
            SequentialLocalAdbServerEndpointAllocator.__module__,
            "adb.server.provisioning",
        )

    def test_server_supervision_namespace_is_canonical(self) -> None:
        self.assertEqual(
            AdbServerSupervisionPolicy.__module__,
            "adb.supervision.model",
        )
        self.assertEqual(
            AdbServerSupervisor.__module__,
            "adb.supervision.server",
        )

    def test_transport_connection_namespace_is_canonical(self) -> None:
        self.assertEqual(AdbTcpConnect.__module__, "adb.transport.connection.command")
        self.assertEqual(SubprocessAdbTransport.__module__, "adb.transport.connection.adapters")
        self.assertEqual(AdbTcpConnect("192.0.2.1:5555").address, "192.0.2.1:5555")

    def test_devices_observation_namespaces_are_canonical(self) -> None:
        self.assertEqual(
            AdbDevicesObservationEstablishmentPolicy.__module__,
            "adb.transport.observation.establishment",
        )
        self.assertEqual(
            AdbDevicesObservationSupervisionPolicy.__module__,
            "adb.supervision.model",
        )
        self.assertEqual(
            AdbDevicesObservationSupervisor.__module__,
            "adb.supervision.devices_observation",
        )

    def test_managed_runtime_scaffold_is_top_level_adb_api(self) -> None:
        self.assertEqual(AdbManagedRuntime.__module__, "adb.managed")
        self.assertEqual(RegisteredTransport.__module__, "adb.managed")


if __name__ == "__main__":
    unittest.main()
