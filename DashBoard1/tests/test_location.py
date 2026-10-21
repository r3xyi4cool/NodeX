import asyncio
import pytest
from nodex.collector.location import get_current_location
from nodex.sync.supabase_sync import SupabaseSync
from nodex.sync.queue import EventQueue
from nodex.monitor.monitor import SecurityMonitor
from nodex.ble.manager import BLEManager


def test_get_current_location():
    async def _run():
        loc = await get_current_location(timeout=5.0)
        # Note: In environments without GPS or network, loc may be None.
        # But if returned, it MUST be valid coordinates, never fake.
        if loc is not None:
            assert "latitude" in loc
            assert "longitude" in loc
            assert -90.0 <= loc["latitude"] <= 90.0
            assert -180.0 <= loc["longitude"] <= 180.0
            assert "source" in loc
            assert loc["source"] in ("winrt", "ip-api", "ipapi.co")
            assert "timestamp" in loc
            if loc.get("accuracy") is not None:
                assert loc["accuracy"] >= 0.0

    asyncio.run(_run())


def test_sync_location_graceful():
    async def _run():
        queue = EventQueue()
        ble = BLEManager()
        monitor = SecurityMonitor(ble, queue)
        sync = SupabaseSync(queue, monitor)

        # Calling sync_location should never raise unhandled exceptions
        res = await sync.sync_location(sync_event="TEST_SYNC", image_url=None)
        if res is not None:
            assert "latitude" in res
            assert "longitude" in res
            assert res.get("sync_event") == "TEST_SYNC"

    asyncio.run(_run())


def test_location_demo_mode():
    """Verify location tracking operates independently of ESP32 / in Demo Mode."""
    async def _run():
        from nodex.config.settings import settings
        prev_mock = settings.mock_ble
        settings.mock_ble = True
        try:
            queue = EventQueue()
            ble = BLEManager()
            monitor = SecurityMonitor(ble, queue)
            sync = SupabaseSync(queue, monitor)

            # In Demo Mode (no ESP32), sync_location must still execute safely
            res = await sync.sync_location(sync_event="DEMO_SYNC", image_url="https://example.com/demo.jpg")
            if res is not None:
                assert "latitude" in res
                assert "longitude" in res
                assert res.get("image_url") == "https://example.com/demo.jpg"
                assert res.get("sync_event") == "DEMO_SYNC"
        finally:
            settings.mock_ble = prev_mock

    asyncio.run(_run())

