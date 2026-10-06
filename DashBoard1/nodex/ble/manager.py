"""
NodeX BLE Manager
-----------------
Owns the live BLE connection to the ESP32 token.
Implements:
  - Scanning for paired device by address
  - Auto-reconnect with exponential back-off
  - RSSI polling (bleak lacks native RSSI streaming on Windows)
  - RSSI moving-average smoothing
  - Mock mode (simulated RSSI & disconnects) for hardware-free testing

State is exposed via asyncio.Event flags and callbacks consumed by the
monitor state machine.

NOTE: BLE bonding / challenge-response is NOT yet implemented.
      Interface is documented below with TODO markers.
"""
from __future__ import annotations

import asyncio
import logging
import math
import random
import time
from collections import deque
from typing import Callable, Deque, Optional

from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError

from nodex.config.settings import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ESP32 custom GATT UUIDs (update when firmware is finalised)
# TODO: replace placeholders with real UUIDs from ESP32 firmware
# ---------------------------------------------------------------------------
ESP32_SERVICE_UUID = "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
ESP32_CHAR_FIRMWARE = "beb5483e-36e1-4688-b7f5-ea07361b26a8"
ESP32_CHAR_BATTERY = "beb5483e-36e1-4688-b7f5-ea07361b26a9"

# ---------------------------------------------------------------------------
# Type alias for RSSI callback
# ---------------------------------------------------------------------------
RssiCallback = Callable[[int], None]
ConnectCallback = Callable[[], None]
DisconnectCallback = Callable[[], None]


class RssiSmoother:
    """Moving-average filter over a sliding window of RSSI readings."""

    def __init__(self, window: int = 5) -> None:
        self._window: Deque[int] = deque(maxlen=window)

    def add(self, rssi: int) -> float:
        self._window.append(rssi)
        return sum(self._window) / len(self._window)

    @property
    def current(self) -> Optional[float]:
        return sum(self._window) / len(self._window) if self._window else None

    def reset(self) -> None:
        self._window.clear()


# ---------------------------------------------------------------------------
# BLE Manager
# ---------------------------------------------------------------------------

class BLEManager:
    """
    Manages the BLE connection to the ESP32 token.

    Usage
    -----
    manager = BLEManager()
    manager.on_connected = my_connect_cb
    manager.on_disconnected = my_disconnect_cb
    manager.on_rssi = my_rssi_cb
    await manager.start()          # non-blocking; runs reconnect loop
    ...
    await manager.stop()
    """

    RSSI_POLL_INTERVAL = 2.0       # seconds between RSSI reads
    BACKOFF_BASE = 2.0             # exponential back-off base (seconds)
    BACKOFF_MAX = 60.0             # max back-off cap

    def __init__(self) -> None:
        self._client: Optional[BleakClient] = None
        self._task: Optional[asyncio.Task] = None
        self._rssi_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

        self.smoother = RssiSmoother(settings.rssi_window_size)
        self.connected = False
        self.rssi: Optional[int] = None
        self.rssi_smooth: Optional[float] = None
        self.firmware_version: Optional[str] = None
        self.device_battery: Optional[int] = None
        self.last_seen: Optional[float] = None

        # Callbacks — set by monitor.py
        self.on_connected: Optional[ConnectCallback] = None
        self.on_disconnected: Optional[DisconnectCallback] = None
        self.on_rssi: Optional[RssiCallback] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the reconnect loop (non-blocking)."""
        self._stop_event.clear()
        if settings.mock_ble:
            self._task = asyncio.create_task(self._mock_loop(), name="ble-mock")
        else:
            self._task = asyncio.create_task(self._reconnect_loop(), name="ble-reconnect")
        logger.info("BLE manager started (mock=%s)", settings.mock_ble)

    async def stop(self) -> None:
        """Signal the reconnect loop to stop and clean up."""
        self._stop_event.set()
        if self._rssi_task:
            self._rssi_task.cancel()
        if self._task:
            self._task.cancel()
        if self._client and self._client.is_connected:
            try:
                await self._client.disconnect()
            except Exception:
                pass
        self.connected = False
        logger.info("BLE manager stopped")

    async def scan(self, duration: float = 10.0) -> list[dict]:
        """
        Scan for nearby BLE devices and return a list of dicts.
        Filters for devices likely to be ESP32 (by name prefix or all if none).
        """
        logger.info("Starting BLE scan (%.1f s)…", duration)
        found = []
        try:
            devices = await BleakScanner.discover(timeout=duration)
            for d in devices:
                found.append({
                    "address": d.address,
                    "name": d.name or "(unknown)",
                    "rssi": d.rssi,
                })
            logger.info("Scan found %d devices", len(found))
        except BleakError as exc:
            logger.error("BLE scan error: %s", exc)
        return found

    def pair(self, address: str, name: str) -> None:
        """
        Store the chosen device address so the reconnect loop targets it.

        TODO: BLE Bonding / Challenge-Response
        ----------------------------------------
        Full BLE bonding requires the platform to store LTK (Long Term Keys).
        On Windows, this happens automatically when pairing via the OS Bluetooth
        settings.  To implement application-level challenge-response:
          1. Define a custom GATT characteristic on the ESP32 for a HMAC nonce.
          2. On connect, write a random nonce to that characteristic.
          3. Read the response; verify against shared secret stored in keyring.
          4. Reject the connection if verification fails.
        Interface stub:
            async def _challenge_response(self, client: BleakClient) -> bool:
                ...  # returns True if authenticated
        """
        settings.paired_device_address = address
        settings.paired_device_name = name
        logger.info("Paired with device %s (%s)", name, address)

    # ------------------------------------------------------------------
    # Internal — real BLE
    # ------------------------------------------------------------------

    async def _reconnect_loop(self) -> None:
        attempt = 0
        while not self._stop_event.is_set():
            address = settings.paired_device_address
            if not address:
                logger.debug("No paired device address — waiting…")
                await asyncio.sleep(5)
                continue

            try:
                await self._connect(address)
                attempt = 0  # reset back-off on success
            except asyncio.CancelledError:
                break
            except Exception as exc:
                self._handle_disconnect()
                wait = min(self.BACKOFF_BASE ** attempt, self.BACKOFF_MAX)
                logger.warning(
                    "BLE connect failed (%s). Retry in %.0f s (attempt %d).",
                    exc, wait, attempt + 1,
                )
                attempt += 1
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(), timeout=wait
                    )
                except asyncio.TimeoutError:
                    pass

    async def _connect(self, address: str) -> None:
        logger.info("Connecting to %s…", address)
        async with BleakClient(
            address,
            disconnected_callback=self._on_ble_disconnect,
        ) as client:
            self._client = client
            self._handle_connect()

            # Read optional GATT characteristics
            await self._read_device_info(client)

            # Start RSSI polling
            self._rssi_task = asyncio.create_task(
                self._rssi_poll_loop(client), name="ble-rssi"
            )
            try:
                # Keep connection open until disconnected or stop requested
                await self._stop_event.wait()
            finally:
                self._rssi_task.cancel()
                with asyncio.suppress(asyncio.CancelledError):
                    await self._rssi_task

    async def _read_device_info(self, client: BleakClient) -> None:
        """Attempt to read firmware and battery from GATT (best-effort)."""
        try:
            services = client.services
            fw_char = services.get_characteristic(ESP32_CHAR_FIRMWARE)
            if fw_char:
                raw = await client.read_gatt_char(fw_char)
                self.firmware_version = raw.decode("utf-8", errors="ignore").strip()
                settings.paired_device_firmware = self.firmware_version
                logger.info("ESP32 firmware: %s", self.firmware_version)
        except Exception as exc:
            logger.debug("Could not read firmware char: %s", exc)
        try:
            services = client.services
            bat_char = services.get_characteristic(ESP32_CHAR_BATTERY)
            if bat_char:
                raw = await client.read_gatt_char(bat_char)
                self.device_battery = int.from_bytes(raw, "little")
                logger.info("ESP32 battery: %d%%", self.device_battery)
        except Exception as exc:
            logger.debug("Could not read battery char: %s", exc)

    async def _rssi_poll_loop(self, client: BleakClient) -> None:
        """Poll RSSI every RSSI_POLL_INTERVAL seconds via BleakClient."""
        while client.is_connected and not self._stop_event.is_set():
            try:
                # bleak 0.22+ exposes get_rssi() on Windows WinRT backend
                rssi = await client.get_rssi()  # type: ignore[attr-defined]
                self.rssi = rssi
                self.rssi_smooth = self.smoother.add(rssi)
                self.last_seen = time.monotonic()
                if self.on_rssi:
                    self.on_rssi(rssi)
                logger.debug("RSSI raw=%d smooth=%.1f", rssi, self.rssi_smooth)
            except AttributeError:
                # Fallback: bleak may not expose get_rssi on all backends
                logger.debug("get_rssi() not available; using last known RSSI")
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("RSSI poll error: %s", exc)
            await asyncio.sleep(self.RSSI_POLL_INTERVAL)

    def _on_ble_disconnect(self, client: BleakClient) -> None:  # noqa: ARG002
        logger.warning("BLE device disconnected unexpectedly")
        self._handle_disconnect()

    def _handle_connect(self) -> None:
        self.connected = True
        self.smoother.reset()
        logger.info("BLE connected to %s", settings.paired_device_address)
        if self.on_connected:
            self.on_connected()

    def _handle_disconnect(self) -> None:
        if self.connected:
            self.connected = False
            self.rssi = None
            self.rssi_smooth = None
            logger.info("BLE disconnected")
            if self.on_disconnected:
                self.on_disconnected()

    # ------------------------------------------------------------------
    # Mock mode — simulates RSSI and random disconnects
    # ------------------------------------------------------------------

    async def _mock_loop(self) -> None:
        """
        Simulate BLE behaviour without hardware.
        RSSI drifts between -45 and -80 dBm with occasional drops to
        below threshold and brief disconnects.
        """
        logger.info("[MOCK] BLE mock mode active")
        mock_rssi: float = -55.0
        connected_duration = 0

        while not self._stop_event.is_set():
            # Simulate occasional disconnect (avg every ~3 min)
            if connected_duration > 0 and random.random() < 0.003:
                logger.info("[MOCK] Simulated BLE disconnect")
                self._handle_disconnect()
                await asyncio.sleep(random.uniform(3, 8))
                self._handle_connect()
                connected_duration = 0
                continue

            if not self.connected:
                await asyncio.sleep(1)
                self._handle_connect()
                connected_duration = 0
                continue

            # Random walk on RSSI
            mock_rssi += random.uniform(-3, 3)
            mock_rssi = max(-95.0, min(-40.0, mock_rssi))
            rssi_int = int(mock_rssi)

            self.rssi = rssi_int
            self.rssi_smooth = self.smoother.add(rssi_int)
            self.last_seen = time.monotonic()
            self.firmware_version = "mock-1.0.0"
            self.device_battery = 87

            if self.on_rssi:
                self.on_rssi(rssi_int)

            connected_duration += 1
            await asyncio.sleep(self.RSSI_POLL_INTERVAL)
