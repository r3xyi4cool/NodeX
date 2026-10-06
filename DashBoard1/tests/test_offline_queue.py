"""
Unit tests for the SQLite-backed EventQueue.
Tests insertion, retrieval, marking synced/error, and SQLite persistence.
"""
import pytest
from nodex.sync.queue import EventQueue


@pytest.fixture
def temp_queue(tmp_path):
    db_file = tmp_path / "test_queue.db"
    return EventQueue(db_path=db_file)


def test_queue_init(temp_queue):
    assert temp_queue.pending_count == 0
    assert temp_queue.last_sync_time is None
    assert temp_queue.last_sync_error is None


def test_enqueue_and_get_events(temp_queue):
    payload = {"state_before": "DISARMED", "state_after": "ARMED", "rssi": -65}
    row_id = temp_queue.enqueue({"event_type": "ARM", **payload}, table="events")
    assert row_id == 1
    assert temp_queue.pending_count == 1

    unsynced = temp_queue.get_unsynced(table="events")
    assert len(unsynced) == 1
    item = unsynced[0]
    assert item["id"] == 1
    assert item["event_type"] == "ARM"
    assert item["payload"]["state_after"] == "ARMED"
    assert item["payload"]["rssi"] == -65


def test_enqueue_heartbeat(temp_queue):
    hb = {"battery_percent": 88, "charging": True, "ble_connected": True}
    row_id = temp_queue.enqueue_heartbeat(hb)
    assert row_id == 1
    assert temp_queue.pending_count == 1

    unsynced = temp_queue.get_unsynced(table="heartbeats")
    assert len(unsynced) == 1
    assert unsynced[0]["payload"]["battery_percent"] == 88


def test_mark_synced(temp_queue):
    row_id = temp_queue.enqueue({"event_type": "TEST"})
    assert temp_queue.pending_count == 1

    temp_queue.mark_synced(row_id, table="events")
    assert temp_queue.pending_count == 0
    assert temp_queue.last_sync_time is not None

    unsynced = temp_queue.get_unsynced(table="events")
    assert len(unsynced) == 0


def test_mark_error(temp_queue):
    row_id = temp_queue.enqueue({"event_type": "TEST"})
    temp_queue.mark_error(row_id, "Supabase HTTP 500", table="events")
    assert temp_queue.last_sync_error == "Supabase HTTP 500"
    # Row is still unsynced
    unsynced = temp_queue.get_unsynced(table="events")
    assert len(unsynced) == 1


def test_queue_persistence(tmp_path):
    db_file = tmp_path / "persistent_queue.db"
    q1 = EventQueue(db_path=db_file)
    q1.enqueue({"event_type": "EVENT_1"})
    q1.enqueue({"event_type": "EVENT_2"})
    assert q1.pending_count == 2

    # Open with a new instance pointing to the same file
    q2 = EventQueue(db_path=db_file)
    assert q2.pending_count == 2
    unsynced = q2.get_unsynced(table="events")
    assert len(unsynced) == 2
    assert unsynced[0]["event_type"] == "EVENT_1"
    assert unsynced[1]["event_type"] == "EVENT_2"
