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
        self._reconnect_trigger = asyncio.Event()

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
        self._reconnect_trigger.set()
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
        Tags devices likely to be ESP32 by name (common prefixes).
        ESP32-likely devices are sorted first in the result list.
        """
        ESP32_NAME_HINTS = ("esp", "nodex", "node-x", "ble-token", "token", "arduino")

        logger.info("Starting BLE scan (%.1f s)…", duration)
        found = []
        try:
            discovered = await BleakScanner.discover(timeout=duration, return_adv=True)
            for dev, adv in discovered.values():
                name = dev.name or ""
                name_lower = name.lower()
                likely_esp32 = (name == "NodeX") or any(h in name_lower for h in ESP32_NAME_HINTS)
                found.append({
                    "address": dev.address,
                    "name": name or "(unknown)",
                    "rssi": adv.rssi,
                    "likely_esp32": likely_esp32,
                })
            # Sort: ESP32 candidates first, then by RSSI descending
            found.sort(key=lambda x: (not x["likely_esp32"], -(x["rssi"] or -999)))
            logger.info("Scan found %d devices (%d likely ESP32)",
                        len(found), sum(1 for d in found if d["likely_esp32"]))
        except Exception as exc:
            logger.error("BLE scan error: %s", exc)
        return found

    def pair(self, address: str, name: str) -> None:
        """
        Store the chosen device address so the reconnect loop targets it.
        """
        settings.paired_device_address = address
        settings.paired_device_name = name
        logger.info("Paired with device %s (%s)", name, address)
        self._reconnect_trigger.set()
        if self._client and self._client.is_connected and self._client.address != address:
            try:
                asyncio.create_task(self._client.disconnect())
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Internal — real BLE
    # ------------------------------------------------------------------

    async def _reconnect_loop(self) -> None:
        attempt = 0
        while not self._stop_event.is_set():
            self._reconnect_trigger.clear()
            address = settings.paired_device_address

            # If no device is paired or currently set to mock address, try auto-discovery
            if not address or address.startswith("MOCK:"):
                logger.info("No paired ESP32 address. Scanning for nearby 'NodeX'...")
                try:
                    devices = await self.scan(duration=5.0)
                    nodex = next((d for d in devices if d.get("name") == "NodeX" or d.get("likely_esp32")), None)
                    if nodex:
                        logger.info("Auto-found ESP32 '%s' at %s! Pairing...", nodex["name"], nodex["address"])
                        self.pair(nodex["address"], nodex["name"])
                        address = nodex["address"]
                except Exception as exc:
                    logger.debug("Auto-scan error: %s", exc)

            if not address or address.startswith("MOCK:"):
                logger.debug("No paired device address — waiting…")
                try:
                    trigger_task = asyncio.create_task(self._reconnect_trigger.wait())
                    stop_task = asyncio.create_task(self._stop_event.wait())
                    done, pending = await asyncio.wait(
                        [trigger_task, stop_task],
                        timeout=5.0,
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    for t in pending:
                        t.cancel()
                except Exception:
                    pass
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
                    trigger_task = asyncio.create_task(self._reconnect_trigger.wait())
                    stop_task = asyncio.create_task(self._stop_event.wait())
                    done, pending = await asyncio.wait(
                        [trigger_task, stop_task],
                        timeout=wait,
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    for t in pending:
                        t.cancel()
                except Exception:
                    pass

    async def _connect(self, address: str) -> None:
        logger.info("Connecting to %s (timeout 20s)…", address)
        disconnected_event = asyncio.Event()

        def _on_disconnect(client: BleakClient) -> None:
            disconnected_event.set()
            self._on_ble_disconnect(client)

        async with BleakClient(
            address,
            timeout=20.0,
            disconnected_callback=_on_disconnect,
        ) as client:
            self._client = client
            self._handle_connect()

            # Read optional GATT characteristics
            await self._read_device_info(client)

            # Start RSSI watcher loop while connected
            self._rssi_task = asyncio.create_task(
                self._rssi_watcher_loop(client, address), name="ble-rssi"
            )
            try:
                # Wait until stop is requested OR the device disconnects
                stop_task = asyncio.create_task(self._stop_event.wait())
                disc_task = asyncio.create_task(disconnected_event.wait())
                done, pending = await asyncio.wait(
                    [stop_task, disc_task],
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for t in pending:
                    t.cancel()
            finally:
                if self._rssi_task:
                    self._rssi_task.cancel()
                    with asyncio.suppress(asyncio.CancelledError):
                        await self._rssi_task

    async def _read_device_info(self, client: BleakClient) -> None:
        """Attempt to read status/firmware and battery from GATT (best-effort)."""
        try:
            services = client.services
            service = services.get_service(ESP32_SERVICE_UUID)
            fw_char = service.get_characteristic(ESP32_CHAR_FIRMWARE) if service else services.get_characteristic(ESP32_CHAR_FIRMWARE)
            if fw_char:
                raw = await client.read_gatt_char(fw_char)
                self.firmware_version = raw.decode("utf-8", errors="ignore").strip()
                settings.paired_device_firmware = self.firmware_version
                logger.info("ESP32 status/firmware: %s", self.firmware_version)
        except Exception as exc:
            logger.debug("Could not read firmware/status char: %s", exc)
        try:
            services = client.services
            service = services.get_service(ESP32_SERVICE_UUID)
            bat_char = service.get_characteristic(ESP32_CHAR_BATTERY) if service else services.get_characteristic(ESP32_CHAR_BATTERY)
            if bat_char:
                raw = await client.read_gatt_char(bat_char)
                self.device_battery = int.from_bytes(raw, "little")
                logger.info("ESP32 battery: %d%%", self.device_battery)
        except Exception as exc:
            logger.debug("Could not read battery char: %s", exc)

    async def _rssi_watcher_loop(self, client: BleakClient, address: str) -> None:
        """
        Stream RSSI updates from BLE advertisements while connected.
        BleakClient lacks get_rssi on Windows WinRT, but BleakScanner
        receives live advertisements from the device with real RSSI values.
        """
        def _adv_callback(dev, adv) -> None:
            if dev.address.upper() == address.upper():
                rssi = adv.rssi
                self.rssi = rssi
                self.rssi_smooth = self.smoother.add(rssi)
                self.last_seen = time.monotonic()
                if self.on_rssi:
                    self.on_rssi(rssi)
                logger.debug("RSSI raw=%d smooth=%.1f", rssi, self.rssi_smooth)

        scanner = BleakScanner(detection_callback=_adv_callback)
        try:
            await scanner.start()
            while client.is_connected and not self._stop_event.is_set():
                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.debug("RSSI watcher notice: %s", exc)
        finally:
            with asyncio.suppress(Exception):
                await scanner.stop()

    def _on_ble_disconnect(self, client: BleakClient) -> None:  # noqa: ARG002
        if not self._stop_event.is_set():
            logger.warning("BLE device disconnected unexpectedly")
        else:
            logger.info("BLE device disconnected normally")
        self._handle_disconnect()

    def _handle_connect(self) -> None:
        self.connected = True
        self.smoother.reset()
        if self.rssi is None:
            # Seed with an initial healthy in-range RSSI until first advertisement arrives
            self.rssi = -50
            self.rssi_smooth = self.smoother.add(-50)
            self.last_seen = time.monotonic()
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
                # In mock mode give a readable placeholder address if none is set
                if not settings.paired_device_address:
                    settings._data["paired_device_address"] = "MOCK:00:00:00:00:00"
                    settings._data["paired_device_name"] = settings._data.get("paired_device_name") or "ESP32-Mock"
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
