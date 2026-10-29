"""
NodeX Monitor — Security Loop
Runs as a long-lived asyncio task.
Reads RSSI from the BLE manager, drives the state machine,
calls LockWorkStation, writes events to the queue, and
triggers alerts.
"""
from __future__ import annotations

import asyncio
import ctypes
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Callable, Optional

from nodex.config.settings import settings
from nodex.monitor.state import SecurityState

if TYPE_CHECKING:
    from nodex.ble.manager import BLEManager
    from nodex.sync.queue import EventQueue

logger = logging.getLogger(__name__)

EventCallback = Callable[[dict], None]  # fired when state changes


class SecurityMonitor:
    """
    Drives the security state machine.
    Must be started after BLEManager.start().
    """

    # How many consecutive sub-threshold readings before entering GRACE_PERIOD
    BAD_READING_THRESHOLD = 3

    def __init__(
        self,
        ble: "BLEManager",
        queue: "EventQueue",
    ) -> None:
        self._ble = ble
        self._queue = queue

        self.state = SecurityState.DISARMED
        self._grace_start: Optional[float] = None
        self._bad_readings = 0
        self._grace_remaining: float = 0.0

        # Disconnection alert & simulation state
        self._active_incident_id: Optional[str] = None
        self._alert_active: bool = False
        self._simulation_active: bool = False
        self._simulated_incident_id: Optional[str] = None

        # Incident & alert callbacks
        self.on_disconnection_incident: Optional[Callable[[dict], None]] = None
        self.on_reconnected: Optional[Callable[[], None]] = None
        self.on_simulation_ended: Optional[Callable[[], None]] = None
        self.on_alert_silenced: Optional[Callable[[], None]] = None

        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

        # Subscribe to BLE events
        self._ble.on_connected = self._on_ble_connected
        self._ble.on_disconnected = self._on_ble_disconnected

        # Callback for UI WebSocket / SSE pushes
        self.on_state_change: Optional[EventCallback] = None

    # ------------------------------------------------------------------
    # Public control API
    # ------------------------------------------------------------------

    async def start(self) -> None:
        self._stop_event.clear()
        self._task = asyncio.create_task(self._monitor_loop(), name="security-monitor")
        logger.info("Security monitor started")

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task:
            self._task.cancel()
        logger.info("Security monitor stopped")

    def arm(self) -> None:
        """Transition to ARMED state (PIN should be verified by caller)."""
        if self.state in (SecurityState.DISARMED, SecurityState.LOCKED):
            self._transition(SecurityState.ARMED, event_type="ARM")
            logger.info("System ARMED")

    def disarm(self) -> None:
        """Transition to DISARMED state (PIN must be verified by caller)."""
        old = self.state
        self._transition(SecurityState.DISARMED, event_type="DISARM")
        self._bad_readings = 0
        self._grace_start = None
        logger.info("System DISARMED (was %s)", old.name)

    def manual_test(self) -> None:
        """Fire a MANUAL_TEST event without actually locking."""
        logger.info("Manual security test triggered")
        self._queue.enqueue({
            "event_type": "MANUAL_TEST",
            "state_before": self.state.name,
            "state_after": self.state.name,
            "rssi": self._ble.rssi,
            "rssi_smooth": self._ble.rssi_smooth,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        if self.on_state_change:
            self.on_state_change(self._build_status())

    @property
    def grace_remaining(self) -> float:
        if self.state == SecurityState.GRACE_PERIOD and self._grace_start:
            elapsed = time.monotonic() - self._grace_start
            return max(0.0, settings.grace_period_seconds - elapsed)
        return 0.0

    # ------------------------------------------------------------------
    # BLE callbacks
    # ------------------------------------------------------------------

    def _on_ble_connected(self) -> None:
        logger.info("BLE connected event received by monitor")
        if self._alert_active and not self._simulation_active:
            self._alert_active = False
            self._active_incident_id = None
            if self.on_reconnected:
                try:
                    self.on_reconnected()
                except Exception as e:
                    logger.debug("on_reconnected callback error: %s", e)

        if self.state in (SecurityState.BLE_LOST, SecurityState.GRACE_PERIOD):
            logger.info("Token recovered during grace period!")
            self._bad_readings = 0
            self._grace_start = None
            self._transition(SecurityState.RECOVERED, event_type="TOKEN_RECOVERED")
            asyncio.get_event_loop().call_later(
                1.0, lambda: self._transition(SecurityState.ARMED, event_type=None)
            )

    def _on_ble_disconnected(self) -> None:
        logger.warning("BLE disconnected event received by monitor")
        if not self._alert_active and not self._simulation_active:
            self._alert_active = True
            inc_id = f"inc-{uuid.uuid4().hex[:8]}"
            self._active_incident_id = inc_id
            incident = {
                "incident_id": inc_id,
                "event_type": "BLE_LOST",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "is_simulation": False,
                "rssi": self._ble.rssi,
                "rssi_smooth": self._ble.rssi_smooth,
                "ble_connected": False,
                "state_before": self.state.name,
                "state_after": SecurityState.BLE_LOST.name,
            }
            if self.on_disconnection_incident:
                try:
                    self.on_disconnection_incident(incident)
                except Exception as e:
                    logger.debug("on_disconnection_incident callback error: %s", e)

        if self.state == SecurityState.ARMED:
            logger.warning("BLE lost while ARMED — starting bad-reading count")

    # ------------------------------------------------------------------
    # Main monitor loop
    # ------------------------------------------------------------------

    async def _monitor_loop(self) -> None:
        logger.info("Monitor loop running every 1 s")
        while not self._stop_event.is_set():
            try:
                await self._tick()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.exception("Monitor loop error: %s", exc)
            await asyncio.sleep(1.0)

    async def _tick(self) -> None:
        """One tick of the monitor loop — called every second."""
        if self.state == SecurityState.DISARMED:
            return
        if self.state == SecurityState.LOCKED:
            return

        # ---- Determine current signal quality ----
        rssi = self._ble.rssi_smooth
        threshold = settings.rssi_threshold

        signal_ok = (
            self._ble.connected
            and rssi is not None
            and rssi >= threshold
        )

        # ---- State transitions ----
        if self.state == SecurityState.ARMED:
            if not signal_ok:
                self._bad_readings += 1
                logger.debug("Bad reading %d/%d (rssi=%.1f)",
                             self._bad_readings, self.BAD_READING_THRESHOLD, rssi or 0)
                if self._bad_readings >= self.BAD_READING_THRESHOLD:
                    self._transition(SecurityState.BLE_LOST, event_type="BLE_LOST")
            else:
                self._bad_readings = 0

        elif self.state == SecurityState.BLE_LOST:
            if signal_ok:
                self._bad_readings = 0
                self._transition(SecurityState.ARMED, event_type="BLE_RECOVERED_FAST")
            else:
                # Immediately move to grace period
                self._grace_start = time.monotonic()
                self._transition(SecurityState.GRACE_PERIOD, event_type="GRACE_STARTED")

        elif self.state == SecurityState.GRACE_PERIOD:
            if signal_ok:
                self._bad_readings = 0
                self._grace_start = None
                self._transition(SecurityState.RECOVERED, event_type="TOKEN_RECOVERED")
                await asyncio.sleep(1)
                self._transition(SecurityState.ARMED, event_type=None)
            else:
                grace_start = self._grace_start if self._grace_start is not None else time.monotonic()
                elapsed = time.monotonic() - grace_start
                remaining = settings.grace_period_seconds - elapsed
                self._grace_remaining = max(0.0, remaining)
                logger.debug("Grace period: %.1f s remaining", self._grace_remaining)
                if remaining <= 0:
                    await self._trigger_security_event()

        # Always notify UI on tick so grace countdown updates
        if self.on_state_change:
            self.on_state_change(self._build_status())

    # ------------------------------------------------------------------
    # Disconnection Simulation (Demo Hotkey Support)
    # ------------------------------------------------------------------

    @property
    def alert_active(self) -> bool:
        return self._alert_active

    @property
    def simulation_active(self) -> bool:
        return self._simulation_active

    @property
    def active_incident_id(self) -> Optional[str]:
        return self._simulated_incident_id if self._simulation_active else self._active_incident_id

    @property
    def simulated_incident_id(self) -> Optional[str]:
        return self._simulated_incident_id

    @property
    def last_incident_time(self) -> Optional[str]:
        return self._last_incident_time

    def simulate_disconnection(self) -> dict:
        """
        Simulate a beacon disconnection in both Demo Mode and Real Mode.
        Works without modifying actual BLE connection state in Real Mode.
        Guards against duplicate incident triggers while simulation is active.
        """
        if self._simulation_active and self._simulated_incident_id:
            logger.warning("Disconnection simulation already active — returning current incident")
            return {
                "incident_id": self._simulated_incident_id,
                "is_simulation": True,
                "simulated": True,
                "already_active": True,
            }

        self._simulation_active = True
        self._alert_active = True
        sim_id = f"sim-{uuid.uuid4().hex[:8]}"
        self._simulated_incident_id = sim_id

        sim_incident = {
            "incident_id": sim_id,
            "event_type": "SIMULATED_BLE_LOST",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "is_simulation": True,
            "simulated": True,
            "rssi": self._ble.rssi if not settings.mock_ble else -85,
            "rssi_smooth": self._ble.rssi_smooth if not settings.mock_ble else -82.4,
            "ble_connected": self._ble.connected,
            "state_before": self.state.name,
            "state_after": "SIMULATED_DISCONNECT",
            "metadata": {"simulated": True, "is_simulation": True},
        }

        logger.info("[DEMO HOTKEY] Triggered simulated disconnection alert (id=%s)", sim_id)
        if self.on_disconnection_incident:
            try:
                self.on_disconnection_incident(sim_incident)
            except Exception as e:
                logger.debug("on_disconnection_incident error for simulation: %s", e)

        if self.on_state_change:
            self.on_state_change(self._build_status())

        return sim_incident

    def end_simulation(self) -> bool:
        """
        End the active simulated disconnection and return to normal monitoring.
        Does not falsely report physical reconnection.
        """
        if not self._simulation_active:
            return False

        logger.info("[DEMO HOTKEY] Ending simulated disconnection (id=%s)", self._simulated_incident_id)
        self._simulation_active = False
        self._alert_active = False
        self._simulated_incident_id = None

        if self.on_simulation_ended:
            try:
                self.on_simulation_ended()
            except Exception as e:
                logger.debug("on_simulation_ended callback error: %s", e)

        if self.on_state_change:
            self.on_state_change(self._build_status())

        return True

    def silence_alert(self) -> bool:
        """Acknowledge and silence the warning sound for active alert without faking reconnection."""
        logger.info("Alert silenced by user PIN verification")
        self._alert_active = False
        if self.on_alert_silenced:
            try:
                self.on_alert_silenced()
            except Exception as e:
                logger.debug("on_alert_silenced callback error: %s", e)
        if self.on_state_change:
            self.on_state_change(self._build_status())
        return True

    # ------------------------------------------------------------------
    # Security event
    # ------------------------------------------------------------------

    async def _trigger_security_event(self) -> None:
        logger.critical("SECURITY EVENT — locking workstation!")
        self._transition(SecurityState.SECURITY_EVENT, event_type="SECURITY_EVENT")

        event_data = {
            "event_type": "SECURITY_EVENT",
            "state_before": SecurityState.GRACE_PERIOD.name,
            "state_after": SecurityState.LOCKED.name,
            "rssi": self._ble.rssi,
            "rssi_smooth": self._ble.rssi_smooth,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._queue.enqueue(event_data)

        # Lock Windows workstation
        try:
            ctypes.windll.user32.LockWorkStation()
            logger.info("LockWorkStation called")
        except Exception as exc:
            logger.error("Failed to lock workstation: %s", exc)

        self._transition(SecurityState.LOCKED, event_type=None)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _transition(self, new_state: SecurityState, event_type: Optional[str]) -> None:
        old = self.state
        self.state = new_state
        if event_type:
            self._queue.enqueue({
                "event_type": event_type,
                "state_before": old.name,
                "state_after": new_state.name,
                "rssi": self._ble.rssi,
                "rssi_smooth": self._ble.rssi_smooth,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        logger.info("State: %s → %s", old.name, new_state.name)
        if self.on_state_change:
            self.on_state_change(self._build_status())

    def _build_status(self) -> dict:
        return {
            "type": "status",
            "state": self.state.name,
            "state_label": self.state.label(),
            "state_css": self.state.css_class(),
            "ble_connected": self._ble.connected,
            "rssi": self._ble.rssi,
            "rssi_smooth": round(self._ble.rssi_smooth, 1) if self._ble.rssi_smooth else None,
            "grace_remaining": round(self.grace_remaining, 1),
            "paired_name": settings.paired_device_name,
            "paired_address": settings.paired_device_address,
            "firmware": self._ble.firmware_version,
            "esp32_battery": self._ble.device_battery,
            "grace_period": settings.grace_period_seconds,
            "rssi_threshold": settings.rssi_threshold,
            "alert_active": self._alert_active or self._simulation_active,
            "simulation_active": self._simulation_active,
            "active_incident_id": self._simulated_incident_id if self._simulation_active else self._active_incident_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
