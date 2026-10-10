"""
NodeX Dashboard 1 — Main Entry Point
=====================================
Wires together:
  - Single-instance lock (mutex)
  - BLE manager
  - Security monitor
  - Data collector (heartbeats)
  - Supabase sync engine
  - Alert manager (Telegram)
  - FastAPI UI server
  - System tray (minimize-to-tray, no quit on close)

Run with:
    python main.py
    python main.py --mock     # hardware-free testing
    python main.py --no-tray  # headless / no tray icon
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
import threading
import webbrowser
import ctypes
from pathlib import Path
from typing import Optional

# ── Ensure DashBoard1 root is on sys.path ──────────────────────────────────
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

# ── Logging (must be set up before any other imports that log) ─────────────
from nodex.config.logging_setup import setup_logging
setup_logging()
logger = logging.getLogger("nodex.main")

# ── Other imports ──────────────────────────────────────────────────────────
from nodex.config.settings import settings
from nodex.ble.manager import BLEManager
from nodex.monitor.monitor import SecurityMonitor
from nodex.sync.queue import EventQueue
from nodex.sync.supabase_sync import SupabaseSync
from nodex.alerts.alerts import AlertManager, TelegramAlert
from nodex.collector.camera import CameraManager
from nodex.ui.server import NodeXUIServer
from nodex.ui.tray import TrayApp

# ---------------------------------------------------------------------------
# Single-instance lock (Windows named mutex)
# ---------------------------------------------------------------------------

MUTEX_NAME = "Global\\NodeX_Dashboard1_Singleton"


def acquire_single_instance() -> bool:
    """
    Try to create a named Windows mutex.
    Returns True if this is the first instance, False if another is running.
    """
    handle = ctypes.windll.kernel32.CreateMutexW(None, True, MUTEX_NAME)
    error = ctypes.windll.kernel32.GetLastError()
    if error == 183:  # ERROR_ALREADY_EXISTS
        return False
    return True


def focus_existing_window() -> None:
    """Attempt to open the browser to the running instance's dashboard."""
    webbrowser.open(f"http://127.0.0.1:{settings.ui_port}")


# ---------------------------------------------------------------------------
# Application class
# ---------------------------------------------------------------------------

class NodeXApp:
    def __init__(self, mock_ble: bool = False, no_tray: bool = False) -> None:
        if mock_ble:
            settings.mock_ble = True
        else:
            settings.mock_ble = False

        self._no_tray = no_tray
        self._loop: asyncio.AbstractEventLoop | None = None
        self._camera_task: Optional[asyncio.Task] = None
        self._demo_task: Optional[asyncio.Task] = None

        # Wire up components
        self.queue   = EventQueue()
        self.ble     = BLEManager()
        self.monitor = SecurityMonitor(self.ble, self.queue)
        self.sync    = SupabaseSync(self.queue, self.monitor)
        self.alerts  = AlertManager(self.queue)
        self.camera  = CameraManager()
        self.ui      = NodeXUIServer(self.ble, self.monitor, self.queue, self.alerts, camera=self.camera)
        self.tray    = TrayApp(self.monitor, settings.ui_port) if not no_tray else None

        # Wire alerts and camera snap to monitor security events
        original_transition = self.monitor._transition

        def _patched_transition(new_state, event_type):
            original_transition(new_state, event_type)
            from nodex.monitor.state import SecurityState
            if new_state == SecurityState.SECURITY_EVENT and event_type:
                asyncio.ensure_future(
                    self.alerts.fire({
                        "event_type": event_type,
                        "state_after": new_state.name,
                        "rssi_smooth": self.ble.rssi_smooth,
                    })
                )
                async def _snap_emergency():
                    snap = await self.camera.capture_next()
                    if snap:
                        await self.sync.upload_capture(snap)
                asyncio.create_task(_snap_emergency())

        self.monitor._transition = _patched_transition  # type: ignore[method-assign]

        # Wire tray icon updates
        if self.tray:
            original_on_change = self.monitor.on_state_change

            def _tray_update(status: dict):
                if original_on_change:
                    original_on_change(status)
                from nodex.monitor.state import SecurityState
                try:
                    s = SecurityState[status.get("state", "DISARMED")]
                    self.tray.update_icon(s)  # type: ignore[union-attr]
                except (KeyError, Exception):
                    pass

            self.monitor.on_state_change = _tray_update

        # Wire TelegramAlert
        self.alerts.register(TelegramAlert(self.queue))

    async def _start_async(self) -> None:
        logger.info("Starting NodeX Dashboard 1...")

        # Start BLE manager
        await self.ble.start()

        # Start security monitor
        await self.monitor.start()

        # Start UI server (opens browser)
        await self.ui.start(open_browser=True)

        # Start Supabase sync
        await self.sync.start()

        # Start periodic camera capture loop (every 30s when armed/locked)
        self._camera_task = asyncio.create_task(self._camera_loop(), name="camera-surveillance")

        # Start demo simulation generator if in mock/demo mode
        if settings.mock_ble:
            self._demo_task = asyncio.create_task(self._demo_loop(), name="demo-simulator")

        logger.info("All systems started successfully")

    async def _demo_loop(self) -> None:
        """Periodic simulation loop for hardware-free demo mode."""
        from datetime import datetime, timezone
        logger.info("[DEMO] Starting simulated telemetry and security event generator")
        await asyncio.sleep(2.0)

        # 1. Take initial demo camera photo so captures table & gallery are populated immediately
        try:
            initial_snap = await self.camera.capture_next()
            if initial_snap:
                await self.sync.upload_capture(initial_snap)
        except Exception as e:
            logger.debug("[DEMO] Initial camera snap note: %s", e)

        # 2. Seed initial events if queue is empty
        now_iso = datetime.now(timezone.utc).isoformat()
        self.queue.enqueue({
            "event_type": "ARM",
            "state_before": "DISARMED",
            "state_after": "ARMED",
            "rssi": -54,
            "rssi_smooth": -55.2,
            "timestamp": now_iso,
        })
        self.queue.enqueue({
            "event_type": "MANUAL_TEST",
            "state_before": "ARMED",
            "state_after": "ARMED",
            "rssi": -58,
            "rssi_smooth": -56.8,
            "timestamp": now_iso,
        })
        self.queue.enqueue({
            "event_type": "ALERT_TELEGRAM",
            "alert_type": "telegram",
            "original_event": "MANUAL_TEST",
            "success": True,
            "error": None,
            "timestamp": now_iso,
        })

        # 3. Simulate periodic walk-aways, recoveries, and captures every 35s
        demo_cycle = 0
        while True:
            try:
                await asyncio.sleep(35.0)
                demo_cycle += 1
                cycle_type = demo_cycle % 3
                ts = datetime.now(timezone.utc).isoformat()

                if cycle_type == 1:
                    logger.info("[DEMO] Simulating token walk-away event...")
                    self.queue.enqueue({
                        "event_type": "BLE_LOST",
                        "state_before": "ARMED",
                        "state_after": "BLE_LOST",
                        "rssi": -85,
                        "rssi_smooth": -82.4,
                        "timestamp": ts,
                    })
                    photo = await self.camera.capture_next()
                    if photo:
                        await self.sync.upload_capture(photo)

                elif cycle_type == 2:
                    logger.info("[DEMO] Simulating token recovered event...")
                    self.queue.enqueue({
                        "event_type": "TOKEN_RECOVERED",
                        "state_before": "GRACE_PERIOD",
                        "state_after": "ARMED",
                        "rssi": -52,
                        "rssi_smooth": -54.0,
                        "timestamp": ts,
                    })

                else:
                    logger.info("[DEMO] Simulating routine test verification...")
                    self.queue.enqueue({
                        "event_type": "MANUAL_TEST",
                        "state_before": "ARMED",
                        "state_after": "ARMED",
                        "rssi": -56,
                        "rssi_smooth": -55.5,
                        "timestamp": ts,
                    })
                    photo = await self.camera.capture_next()
                    if photo:
                        await self.sync.upload_capture(photo)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("[DEMO] Simulation loop error: %s", exc)

    async def _camera_loop(self) -> None:
        """Periodic 30-second camera capture loop with 20-photo circular buffer."""
        from nodex.monitor.state import SecurityState
        logger.info("Webcam surveillance loop active (every %d s)", settings.camera_interval_seconds)
        while True:
            try:
                await asyncio.sleep(settings.camera_interval_seconds)
                # Only capture when armed or under security event/lock to respect privacy when DISARMED
                if self.monitor.state != SecurityState.DISARMED:
                    photo = await self.camera.capture_next()
                    if photo:
                        await self.sync.upload_capture(photo)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("Camera surveillance loop error: %s", exc)

    async def _stop_async(self) -> None:
        logger.info("Shutting down...")
        if self._demo_task:
            self._demo_task.cancel()
        if self._camera_task:
            self._camera_task.cancel()
        await self.sync.stop()
        await self.monitor.stop()
        await self.ble.stop()
        await self.ui.stop()
        logger.info("Shutdown complete")

    def run(self) -> None:
        # Create event loop
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        # Handle SIGINT / SIGTERM gracefully
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                self._loop.add_signal_handler(sig, self._request_shutdown)
            except NotImplementedError:
                pass  # Windows doesn't fully support signal handlers in asyncio

        # Start tray in a separate daemon thread (pystray blocks)
        if self.tray:
            self.tray.setup(self._loop)
            tray_thread = threading.Thread(target=self.tray.run, daemon=True, name="tray")
            tray_thread.start()

        try:
            self._loop.run_until_complete(self._start_async())
            self._loop.run_forever()
        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt received")
        finally:
            self._loop.run_until_complete(self._stop_async())
            if self.tray:
                self.tray.stop()
            self._loop.close()
            logger.info("NodeX exited cleanly")

    def _request_shutdown(self) -> None:
        from nodex.monitor.state import SecurityState
        if self.monitor.state == SecurityState.ARMED:
            logger.warning("Shutdown blocked — system is ARMED. Disarm first.")
            return
        logger.info("Shutdown requested")
        if self._loop:
            self._loop.stop()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="NodeX Dashboard 1")
    parser.add_argument("--mock",    action="store_true", help="Use mock BLE (no hardware)")
    parser.add_argument("--demo",    action="store_true", help="Run in demo mode (simulates proximity events & syncs to Supabase)")
    parser.add_argument("--no-tray", action="store_true", help="Disable system tray")
    args = parser.parse_args()

    # Single-instance check
    if not acquire_single_instance():
        logger.warning("NodeX is already running — focusing existing window")
        focus_existing_window()
        sys.exit(0)

    is_demo = args.mock or args.demo
    app = NodeXApp(mock_ble=is_demo, no_tray=args.no_tray)
    app.run()


if __name__ == "__main__":
    main()
