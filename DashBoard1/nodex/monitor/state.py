"""
NodeX Security State Machine
------------------------------
States:
    DISARMED      → System is idle; BLE loss has no consequence.
    ARMED         → Monitoring active; BLE loss starts grace period.
    BLE_LOST      → Token dropped below RSSI threshold; timer running.
    GRACE_PERIOD  → Explicit countdown before action.
    SECURITY_EVENT→ Lock has been triggered.
    RECOVERED     → Token re-appeared during grace; back to ARMED.
    LOCKED        → LockWorkStation called.

Allowed transitions:
    DISARMED       → ARMED           (arm command)
    ARMED          → DISARMED        (disarm command, PIN verified)
    ARMED          → BLE_LOST        (RSSI < threshold)
    BLE_LOST       → ARMED           (RSSI recovered)
    BLE_LOST       → GRACE_PERIOD    (after 3 consecutive bad readings)
    GRACE_PERIOD   → ARMED           (RSSI recovered during grace)
    GRACE_PERIOD   → SECURITY_EVENT  (grace timer expired)
    SECURITY_EVENT → LOCKED          (lock executed)
    LOCKED         → DISARMED        (manual unlock, token re-paired)
"""
from __future__ import annotations

from enum import Enum, auto


class SecurityState(Enum):
    DISARMED = auto()
    ARMED = auto()
    BLE_LOST = auto()
    GRACE_PERIOD = auto()
    SECURITY_EVENT = auto()
    RECOVERED = auto()
    LOCKED = auto()

    def label(self) -> str:
        return self.name.replace("_", " ")

    def css_class(self) -> str:
        mapping = {
            SecurityState.DISARMED: "disarmed",
            SecurityState.ARMED: "armed",
            SecurityState.BLE_LOST: "ble-lost",
            SecurityState.GRACE_PERIOD: "grace",
            SecurityState.SECURITY_EVENT: "event",
            SecurityState.RECOVERED: "armed",
            SecurityState.LOCKED: "locked",
        }
        return mapping.get(self, "disarmed")
