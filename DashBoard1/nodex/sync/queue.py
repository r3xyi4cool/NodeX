"""
NodeX Offline Event Queue
--------------------------
SQLite-backed queue that stores every event and heartbeat locally first.
Sync engine picks up rows with synced=0 and marks them synced=1 on success.
Events are NEVER deleted (audit trail).
Thread-safe: uses a dedicated thread for SQLite via run_in_executor.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from nodex.config.settings import DB_FILE

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type  TEXT    NOT NULL,
    payload     TEXT    NOT NULL,   -- JSON blob
    created_at  TEXT    NOT NULL,
    synced      INTEGER NOT NULL DEFAULT 0,
    synced_at   TEXT,
    error       TEXT
);

CREATE TABLE IF NOT EXISTS heartbeats (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type  TEXT    DEFAULT 'HEARTBEAT',
    payload     TEXT    NOT NULL,
    created_at  TEXT    NOT NULL,
    synced      INTEGER NOT NULL DEFAULT 0,
    synced_at   TEXT,
    error       TEXT
);

CREATE TABLE IF NOT EXISTS alerts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type  TEXT    NOT NULL,   -- e.g. ALERT_TELEGRAM
    payload     TEXT    NOT NULL,   -- JSON blob (alert_type, original_event, success, error)
    created_at  TEXT    NOT NULL,
    synced      INTEGER NOT NULL DEFAULT 0,
    synced_at   TEXT,
    error       TEXT
);
"""


class EventQueue:
    """
    Thread-safe SQLite queue.
    Use enqueue() from any thread/coroutine.
    Use get_unsynced() / mark_synced() from the sync engine.
    """

    def __init__(self, db_path: Path = DB_FILE) -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        self._pending_count: int = 0
        self._last_sync_time: Optional[str] = None
        self._last_sync_error: Optional[str] = None
        self._init_db()

    # ------------------------------------------------------------------
    # Init
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.executescript(_SCHEMA)
        self._pending_count = self._count_unsynced()
        logger.info("EventQueue ready at %s (%d pending)", self._db_path, self._pending_count)

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def enqueue(self, event: dict, table: str = "events") -> int:
        """Insert an event and return its row id."""
        now = datetime.now(timezone.utc).isoformat()
        payload = json.dumps(event, ensure_ascii=False)
        event_type = event.get("event_type", "UNKNOWN")

        with self._lock:
            with self._get_conn() as conn:
                cur = conn.execute(
                    f"INSERT INTO {table} (event_type, payload, created_at) VALUES (?,?,?)",
                    (event_type, payload, now),
                )
                row_id = cur.lastrowid
            self._pending_count += 1

        logger.debug("Enqueued %s (id=%d, table=%s)", event_type, row_id, table)
        return row_id  # type: ignore[return-value]

    def enqueue_heartbeat(self, payload: dict) -> int:
        return self.enqueue(payload, table="heartbeats")

    # ------------------------------------------------------------------
    # Read / mark
    # ------------------------------------------------------------------

    def get_unsynced(self, table: str = "events", limit: int = 50) -> list[dict]:
        with self._lock:
            with self._get_conn() as conn:
                rows = conn.execute(
                    f"SELECT id, event_type, payload, created_at FROM {table} "
                    f"WHERE synced=0 ORDER BY id ASC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [
            {
                "id": r["id"],
                "event_type": r["event_type"],
                "payload": json.loads(r["payload"]),
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    def mark_synced(self, row_id: int, table: str = "events") -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    f"UPDATE {table} SET synced=1, synced_at=? WHERE id=?",
                    (now, row_id),
                )
            self._pending_count = max(0, self._pending_count - 1)
        self._last_sync_time = now

    def mark_error(self, row_id: int, error: str, table: str = "events") -> None:
        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    f"UPDATE {table} SET error=? WHERE id=?",
                    (error[:500], row_id),
                )
        self._last_sync_error = error

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def _count_unsynced(self) -> int:
        with self._get_conn() as conn:
            ev = conn.execute("SELECT COUNT(*) FROM events WHERE synced=0").fetchone()[0]
            hb = conn.execute("SELECT COUNT(*) FROM heartbeats WHERE synced=0").fetchone()[0]
            al = conn.execute("SELECT COUNT(*) FROM alerts WHERE synced=0").fetchone()[0]
        return ev + hb + al

    @property
    def pending_count(self) -> int:
        return self._pending_count

    @property
    def last_sync_time(self) -> Optional[str]:
        return self._last_sync_time

    @property
    def last_sync_error(self) -> Optional[str]:
        return self._last_sync_error

    def status_dict(self) -> dict:
        return {
            "pending": self.pending_count,
            "last_sync": self.last_sync_time,
            "last_error": self.last_sync_error,
        }
