import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from nodex.config.settings import Settings, settings, CONFIG_FILE
from nodex.sync.supabase_sync import SupabaseSync
from nodex.monitor.monitor import SecurityMonitor
from nodex.ble.manager import BLEManager
from nodex.sync.queue import EventQueue


def test_session_pin_security_and_non_persistence(tmp_path):
    """Verify session PIN is stored in salted memory only and never written to disk."""
    test_cfg = tmp_path / "test_config.json"
    s = Settings(path=test_cfg)

    # Initially has_pin should be False
    assert not s.has_pin()

    # Set PIN
    s.set_pin("5678")
    assert s.has_pin()
    assert s.verify_pin("5678")
    assert not s.verify_pin("0000")
    assert not s.verify_pin("")

    # Save to disk
    s.save()
    disk_content = test_cfg.read_text(encoding="utf-8")
    assert "arm_pin_hash" not in disk_content
    assert "5678" not in disk_content

    # Clear PIN
    s.clear_pin()
    assert not s.has_pin()


def test_disconnection_simulation_and_idempotency():
    """Verify simulate_disconnection triggers simulated incident without touching physical BLE."""
    ble = BLEManager()
    queue = EventQueue()
    mon = SecurityMonitor(ble, queue)

    incident_fired = []
    mon.on_disconnection_incident = lambda inc: incident_fired.append(inc)

    # 1. Trigger simulation
    incident = mon.simulate_disconnection()
    assert mon.simulation_active
    assert mon.alert_active
    assert incident["simulated"] is True
    assert len(incident_fired) == 1
    assert incident_fired[0]["incident_id"] == incident["incident_id"]

    # 2. Duplicate trigger while active should return existing incident without double-firing
    incident2 = mon.simulate_disconnection()
    assert incident2["incident_id"] == incident["incident_id"]
    assert len(incident_fired) == 1

    # 3. Silence alert
    assert mon.silence_alert() is True
    assert not mon.alert_active
    assert mon.simulation_active  # Simulation still active until explicitly ended
    assert ble.connected is False # Physical BLE state is unchanged

    # 4. End simulation
    assert mon.end_simulation() is True
    assert not mon.simulation_active
    assert not mon.alert_active


def test_supabase_manual_upload_all():
    """Verify upload_all_now coordinates telemetry, queue flushing, photo upload, and verification."""
    async def _run():
        queue = EventQueue()
        ble = BLEManager()
        mon = SecurityMonitor(ble, queue)
        sync = SupabaseSync(queue, mon)

        # Enqueue a dummy event
        queue.enqueue({"event_type": "MANUAL_TEST", "timestamp": "2026-10-29T12:00:00Z"})
        assert queue.pending_count >= 1

        # Mock Supabase client
        mock_client = MagicMock()
        mock_client.table().upsert().execute.return_value = MagicMock(data=[{"id": "laptop-1"}])
        mock_client.table().insert().execute.return_value = MagicMock(data=[{"id": "loc-1"}])
        mock_client.table().select().eq().execute.return_value = MagicMock(data=[{"id": "laptop-1"}])
        mock_client.storage.from_().upload.return_value = MagicMock(status_code=200)

        sync._client = mock_client
        sync._auth_ensured = True

        progress_steps = []
        def _on_progress(*args):
            progress_steps.append(args[0] if args else "step")

        result = await sync.upload_all_now(progress_callback=_on_progress)

        assert result["status"] in ("SUCCESS", "PARTIAL")
        assert result["telemetry_synced"] is True
        assert result["verified"] is True
        assert len(progress_steps) > 0

    asyncio.run(_run())
