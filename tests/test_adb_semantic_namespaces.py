from __future__ import annotations

import importlib.util
import unittest

import adb.supervision as supervision
from adb.server import AdbServerStatusReader as PublicServerStatusReader
from adb.server.lifecycle import AdbServerEnsurePolicy, AdbServerStart
from adb.server.lifecycle.adapters import SubprocessAdbServer
from adb.server.status import AdbServerStatus, AdbServerStatusReader
from adb.supervision import (
    AdbTransportInventoryObservationSupervisionPolicy,
    AdbTransportInventoryObservationSupervisor,
)
from adb.transport.connection import AdbTcpConnect
from adb.transport.connection.adapters import SubprocessAdbTransport
from adb.transport.observation import AdbTransportInventoryObservationEstablishmentPolicy


class AdbSemanticNamespaceTests(unittest.TestCase):
    def test_server_status_namespace_is_canonical(self) -> None:
        self.assertIs(AdbServerStatusReader, PublicServerStatusReader)
        self.assertEqual(AdbServerStatus.__module__, "adb.server.status.model")

    def test_server_lifecycle_namespace_is_canonical(self) -> None:
        self.assertEqual(AdbServerStart.__module__, "adb.server.lifecycle.command")
        self.assertEqual(SubprocessAdbServer.__module__, "adb.server.lifecycle.adapters")
        self.assertEqual(AdbServerEnsurePolicy.__module__, "adb.server.lifecycle.ensure")
        self.assertEqual(AdbServerEnsurePolicy(1.0, 0.1).timeout_seconds, 1.0)

    def test_transport_connection_namespace_is_canonical(self) -> None:
        self.assertEqual(AdbTcpConnect.__module__, "adb.transport.connection.command")
        self.assertEqual(SubprocessAdbTransport.__module__, "adb.transport.connection.adapters")
        self.assertEqual(AdbTcpConnect("192.0.2.1:5555").address, "192.0.2.1:5555")

    def test_transport_inventory_observation_namespaces_are_canonical(self) -> None:
        self.assertEqual(
            AdbTransportInventoryObservationEstablishmentPolicy.__module__,
            "adb.transport.observation.establishment",
        )
        self.assertEqual(
            AdbTransportInventoryObservationSupervisionPolicy.__module__,
            "adb.supervision.model",
        )
        self.assertEqual(
            AdbTransportInventoryObservationSupervisor.__module__,
            "adb.supervision.transport_inventory_observation",
        )

    def test_legacy_adb_compatibility_exports_are_removed(self) -> None:
        for namespace in (
            "adb.server.adapters",
            "adb.server.command",
            "adb.server.domain",
            "adb.server.orchestration",
            "adb.server.query",
            "adb.supervision.recovery",
            "adb.supervision.transport_observation",
            "adb.transport.command",
            "adb.transport.observation.recovery",
        ):
            with self.subTest(namespace=namespace):
                self.assertIsNone(importlib.util.find_spec(namespace))
        for name in (
            "AdbServerRecoveryExhausted",
            "AdbServerRecoveryId",
            "AdbServerRecoveryPolicy",
            "AdbServerRecoveryRetryDue",
            "AdbServerRecoverySupervisor",
            "AdbTransportObservationSupervisor",
        ):
            with self.subTest(name=name):
                self.assertFalse(hasattr(supervision, name))


if __name__ == "__main__":
    unittest.main()
