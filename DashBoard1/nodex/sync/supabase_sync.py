"""
NodeX Supabase Sync Engine
---------------------------
• Authenticates with email/password (stored in Credential Manager via keyring).
• Registers / upserts this laptop by hardware fingerprint.
• Pushes unsynced events and heartbeats from the local SQLite queue.
• Sends heartbeats every settings.heartbeat_interval_seconds.
• Retries with exponential backoff when offline.
• NEVER uses the service_role key.
"""
from __future__ import annotations

import asyncio
import logging
import socket
import platform
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

import keyring
from supabase import create_client, Client  # type: ignore

from nodex.config.settings import settings, get_hardware_fingerprint
from nodex.collector.system_info import collect_snapshot

if TYPE_CHECKING:
    from nodex.sync.queue import EventQueue
    from nodex.monitor.monitor import SecurityMonitor

logger = logging.getLogger(__name__)

KEYRING_SERVICE = "NodeX"
KEYRING_USER_PWD = "supabase_password"
KEYRING_USER_REFRESH = "supabase_refresh_token"

# Retry settings
SYNC_INTERVAL = 10          # seconds between sync attempts
BACKOFF_BASE = 2.0
BACKOFF_MAX = 120.0


class SupabaseSync:
    """
    Manages authentication and data sync to Supabase.
    """

    def __init__(self, queue: "EventQueue", monitor: "SecurityMonitor") -> None:
        self._queue = queue
        self._monitor = monitor
        self._client: Optional[Client] = None
        self._authenticated = False
        self._laptop_id: Optional[str] = settings.laptop_id
        self._task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    async def start(self) -> None:
        if not settings.supabase_url or not settings.supabase_anon_key:
            logger.warning("Supabase URL/key not configured — sync disabled")
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._sync_loop(), name="supabase-sync")
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop(), name="supabase-heartbeat")
        logger.info("Supabase sync engine started")

    async def stop(self) -> None:
        self._stop_event.set()
        for t in (self._task, self._heartbeat_task):
            if t:
                t.cancel()

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    async def _ensure_auth(self) -> bool:
        """Authenticate if not already; return True on success."""
        if self._authenticated and self._client:
            return True
        try:
            self._client = create_client(
                settings.supabase_url,
                settings.supabase_anon_key,
            )
            email = settings.nodex_user_email
            password = keyring.get_password(KEYRING_SERVICE, KEYRING_USER_PWD)
            if not email or not password:
                logger.error(
                    "Supabase credentials missing. "
                    "Run setup.py to store password in Credential Manager."
                )
                return False

            resp = self._client.auth.sign_in_with_password(
                {"email": email, "password": password}
            )
            if resp.user is None:
                logger.error("Supabase auth failed — check email/password")
                return False

            self._authenticated = True
            logger.info("Authenticated as %s", email)

            # Register laptop on first run
            await self._register_laptop()
            return True

        except Exception as exc:
            logger.warning("Auth error: %s", exc)
            self._authenticated = False
            return False

    # ------------------------------------------------------------------
    # Laptop registration
    # ------------------------------------------------------------------

    async def _register_laptop(self) -> None:
        """Upsert this laptop into the laptops table by hardware fingerprint."""
        if not self._client:
            return
        fingerprint = get_hardware_fingerprint()
        snapshot = await collect_snapshot()

        laptop_data = {
            "fingerprint": fingerprint,
            "name": socket.gethostname(),
            "os": snapshot["os"],
            "last_seen": datetime.now(timezone.utc).isoformat(),
            "security_mode": self._monitor.state.name,
        }

        try:
            # Upsert by fingerprint (requires unique constraint on fingerprint column)
            resp = (
                self._client.table("laptops")
                .upsert(laptop_data, on_conflict="fingerprint")
                .execute()
            )
            if resp.data:
                laptop_id = resp.data[0].get("id")
                if laptop_id:
                    settings.laptop_id = str(laptop_id)
                    self._laptop_id = str(laptop_id)
                    logger.info("Laptop registered/updated, id=%s", laptop_id)
        except Exception as exc:
            logger.warning("Laptop registration error: %s", exc)

    # ------------------------------------------------------------------
    # Sync loop
    # ------------------------------------------------------------------

    async def _sync_loop(self) -> None:
        attempt = 0
        while not self._stop_event.is_set():
            try:
                ok = await self._ensure_auth()
                if ok:
                    await self._push_events()
                    await self._push_heartbeats()
                    attempt = 0
                else:
                    raise RuntimeError("Not authenticated")
            except asyncio.CancelledError:
                break
            except Exception as exc:
                wait = min(BACKOFF_BASE ** attempt, BACKOFF_MAX)
                logger.warning("Sync failed (%s). Retry in %.0f s.", exc, wait)
                attempt += 1
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=wait)
                except asyncio.TimeoutError:
                    pass
                continue

            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=SYNC_INTERVAL)
            except asyncio.TimeoutError:
                pass

    async def _push_events(self) -> None:
        """Push unsynced events to Supabase events table."""
        if not self._client or not self._laptop_id:
            return
        rows = self._queue.get_unsynced(table="events")
        if not rows:
            return
        logger.debug("Pushing %d events to Supabase", len(rows))
        for row in rows:
            try:
                payload = {
                    "laptop_id": self._laptop_id,
                    "event_type": row["event_type"],
                    "created_at": row["created_at"],
                    **row["payload"],
                }
                self._client.table("events").insert(payload).execute()
                self._queue.mark_synced(row["id"], table="events")
            except Exception as exc:
                logger.warning("Failed to push event %d: %s", row["id"], exc)
                self._queue.mark_error(row["id"], str(exc), table="events")

    async def _push_heartbeats(self) -> None:
        """Push unsynced heartbeats."""
        if not self._client or not self._laptop_id:
            return
        rows = self._queue.get_unsynced(table="heartbeats")
        if not rows:
            return
        for row in rows:
            try:
                payload = {
                    "laptop_id": self._laptop_id,
                    "created_at": row["created_at"],
                    **row["payload"],
                }
                self._client.table("heartbeats").insert(payload).execute()
                self._queue.mark_synced(row["id"], table="heartbeats")
            except Exception as exc:
                logger.warning("Failed to push heartbeat %d: %s", row["id"], exc)
                self._queue.mark_error(row["id"], str(exc), table="heartbeats")

    # ------------------------------------------------------------------
    # Heartbeat loop
    # ------------------------------------------------------------------

    async def _heartbeat_loop(self) -> None:
        """Every N seconds, collect a snapshot and enqueue a heartbeat."""
        while not self._stop_event.is_set():
            try:
                snapshot = await collect_snapshot()
                hb_payload = {
                    "event_type": "HEARTBEAT",
                    "security_mode": self._monitor.state.name,
                    "battery_percent": snapshot["battery_percent"],
                    "charging": snapshot["charging"],
                    "network_online": snapshot["network_online"],
                    "network_ip": snapshot["network_ip"],
                    "ble_connected": self._monitor._ble.connected,
                    "rssi_smooth": self._monitor._ble.rssi_smooth,
                }
                self._queue.enqueue_heartbeat(hb_payload)

                # Also update laptops.last_seen in Supabase directly
                if self._authenticated and self._client and self._laptop_id:
                    try:
                        self._client.table("laptops").update({
                            "last_seen": datetime.now(timezone.utc).isoformat(),
                            "battery_percent": snapshot["battery_percent"],
                            "network_online": snapshot["network_online"],
                            "security_mode": self._monitor.state.name,
                        }).eq("id", self._laptop_id).execute()
                    except Exception as exc:
                        logger.debug("Heartbeat update error: %s", exc)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("Heartbeat collection error: %s", exc)

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=settings.heartbeat_interval_seconds,
                )
            except asyncio.TimeoutError:
                pass

    # ------------------------------------------------------------------
    # Webcam captures upload
    # ------------------------------------------------------------------

    async def upload_capture(self, photo: dict) -> Optional[str]:
        """
        Uploads a webcam photo to the 'intruder-captures' Supabase Storage bucket.
        Uses slot 1..20. Overwrites the file in the bucket when slot wraps around.
        Upserts the slot record in the 'captures' table.
        """
        if not self._client or not self._laptop_id:
            return None

        slot = photo.get("slot", 1)
        storage_path = f"laptops/{self._laptop_id}/photo_{slot}.jpg"
        jpeg_bytes = photo.get("bytes")
        if not jpeg_bytes:
            return None

        try:
            # Upload or overwrite file in the bucket
            storage_client = self._client.storage.from_("intruder-captures")
            try:
                storage_client.upload(
                    path=storage_path,
                    file=jpeg_bytes,
                    file_options={"upsert": "true", "content-type": "image/jpeg"},
                )
            except Exception:
                try:
                    storage_client.update(
                        path=storage_path,
                        file=jpeg_bytes,
                        file_options={"content-type": "image/jpeg"},
                    )
                except Exception as exc2:
                    logger.debug("Storage upload/update fallback note: %s", exc2)

            public_url = storage_client.get_public_url(storage_path)

            # Upsert into captures table (enforces max 20 photos per laptop)
            self._client.table("captures").upsert(
                {
                    "laptop_id": self._laptop_id,
                    "slot": slot,
                    "storage_path": storage_path,
                    "image_url": public_url,
                    "security_mode": self._monitor.state.name,
                    "captured_at": photo.get("captured_at", datetime.now(timezone.utc).isoformat()),
                },
                on_conflict="laptop_id,slot",
            ).execute()

            logger.info("Uploaded capture slot %d to Supabase Storage: %s", slot, storage_path)
            return public_url
        except Exception as exc:
            logger.warning("Failed to upload capture slot %d: %s", slot, exc)
            return None
