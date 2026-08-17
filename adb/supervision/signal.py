from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from adb.configuration import AdbServerId
from adb.supervision.model import AdbTransportInventoryObservationEstablishmentCycleId


@dataclass(frozen=True, slots=True)
class AdbTransportInventoryObservationEstablishmentRetryDue:
    """Signal delivered when one scheduled observation-establishment retry becomes due."""

    server_id: AdbServerId
    cycle_id: AdbTransportInventoryObservationEstablishmentCycleId
    attempt_number: int

    def __post_init__(self) -> None:
        if not isinstance(self.server_id, AdbServerId):
            raise TypeError("server_id must be AdbServerId")
        if not isinstance(
            self.cycle_id,
            AdbTransportInventoryObservationEstablishmentCycleId,
        ):
            raise TypeError(
                "cycle_id must be AdbTransportInventoryObservationEstablishmentCycleId"
            )
        if isinstance(self.attempt_number, bool) or not isinstance(self.attempt_number, int):
            raise TypeError("attempt_number must be an integer")
        if self.attempt_number <= 0:
            raise ValueError("attempt_number must be greater than zero")


@dataclass(frozen=True, slots=True)
class AdbTransportInventoryObservationEstablishmentExhausted:
    """Signal that an observation-establishment cycle exhausted its attempt budget."""

    server_id: AdbServerId
    cycle_id: AdbTransportInventoryObservationEstablishmentCycleId
    attempts: int

    def __post_init__(self) -> None:
        if not isinstance(self.server_id, AdbServerId):
            raise TypeError("server_id must be AdbServerId")
        if not isinstance(
            self.cycle_id,
            AdbTransportInventoryObservationEstablishmentCycleId,
        ):
            raise TypeError(
                "cycle_id must be AdbTransportInventoryObservationEstablishmentCycleId"
            )
        if isinstance(self.attempts, bool) or not isinstance(self.attempts, int):
            raise TypeError("attempts must be an integer")
        if self.attempts <= 0:
            raise ValueError("attempts must be greater than zero")


AdbSupervisionSignal: TypeAlias = (
    AdbTransportInventoryObservationEstablishmentRetryDue
    | AdbTransportInventoryObservationEstablishmentExhausted
)


__all__ = [
    "AdbSupervisionSignal",
    "AdbTransportInventoryObservationEstablishmentExhausted",
    "AdbTransportInventoryObservationEstablishmentRetryDue",
]
