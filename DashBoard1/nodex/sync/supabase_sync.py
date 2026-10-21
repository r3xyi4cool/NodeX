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
                if settings.mock_ble:
                    logger.info("[DEMO] Running in mock/demo mode — proceeding with configured Supabase credentials")
                    self._authenticated = True
                    await self._register_laptop()
                    return True
                logger.error(
                    "Supabase credentials missing. "
                    "Run setup.py to store password in Credential Manager."
                )
                return False

            try:
                resp = self._client.auth.sign_in_with_password(
                    {"email": email, "password": password}
                )
                if resp.user is None and not settings.mock_ble:
                    logger.error("Supabase auth failed — check email/password")
                    return False
            except Exception as auth_err:
                if settings.mock_ble:
                    logger.info("[DEMO] Auth note: %s — continuing in demo mode", auth_err)
                else:
                    raise

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
        """Upsert this laptop into the laptops table with full hardware & location telemetry."""
        if not self._client:
            return
        fingerprint = get_hardware_fingerprint()
        snapshot = await collect_snapshot()

        full_laptop_data = {
            "fingerprint": fingerprint,
            "name": socket.gethostname(),
            "os": snapshot["os"],
            "last_seen": datetime.now(timezone.utc).isoformat(),
            "security_mode": self._monitor.state.name,
            "battery_percent": snapshot.get("battery_percent"),
            "charging": snapshot.get("charging"),
            "network_online": snapshot.get("network_online"),
            "location": snapshot.get("location"),
            "storage_total_gb": snapshot.get("storage_total_gb"),
            "storage_used_gb": snapshot.get("storage_used_gb"),
            "storage_free_gb": snapshot.get("storage_free_gb"),
            "storage_usage_pct": snapshot.get("storage_usage_pct"),
            "ram_total_gb": snapshot.get("ram_total_gb"),
            "ram_used_gb": snapshot.get("ram_used_gb"),
            "ram_usage_pct": snapshot.get("ram_usage_pct"),
            "cpu_model": snapshot.get("cpu_model"),
            "cpu_usage_pct": snapshot.get("cpu_percent"),
            "gpu_model": snapshot.get("gpu_model"),
            "gpu_vram_gb": snapshot.get("gpu_vram_gb"),
            "gpu_usage_pct": snapshot.get("gpu_usage_pct"),
            "display_info": snapshot.get("display_info"),
            "system_specs": snapshot,
        }

        try:
            resp = (
                self._client.table("laptops")
                .upsert(full_laptop_data, on_conflict="fingerprint")
                .execute()
            )
            if resp.data:
                laptop_id = resp.data[0].get("id")
                if laptop_id:
                    settings.laptop_id = str(laptop_id)
                    self._laptop_id = str(laptop_id)
                    logger.info("Laptop registered with full telemetry, id=%s", laptop_id)
        except Exception as exc:
            # Fallback to base columns if new SQL schema columns are not yet executed
            logger.debug("Full telemetry upsert note: %s — falling back to base columns", exc)
            try:
                base_laptop_data = {
                    "fingerprint": fingerprint,
                    "name": socket.gethostname(),
                    "os": snapshot["os"],
                    "last_seen": datetime.now(timezone.utc).isoformat(),
                    "security_mode": self._monitor.state.name,
                    "battery_percent": snapshot.get("battery_percent"),
                    "network_online": snapshot.get("network_online"),
                }
                resp = (
                    self._client.table("laptops")
                    .upsert(base_laptop_data, on_conflict="fingerprint")
                    .execute()
                )
                if resp.data:
                    laptop_id = resp.data[0].get("id")
                    if laptop_id:
                        settings.laptop_id = str(laptop_id)
                        self._laptop_id = str(laptop_id)
                        logger.info("Laptop registered with base columns, id=%s", laptop_id)
            except Exception as exc2:
                logger.warning("Laptop registration error: %s", exc2)

        if not self._laptop_id and self._client:
            try:
                chk = self._client.table("laptops").select("id").eq("fingerprint", fingerprint).execute()
                if chk.data and len(chk.data) > 0:
                    laptop_id = str(chk.data[0]["id"])
                    settings.laptop_id = laptop_id
                    self._laptop_id = laptop_id
                    logger.info("Found existing registered laptop id=%s", laptop_id)
            except Exception as chk_err:
                logger.debug("Laptop ID resolution note: %s", chk_err)

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
                    await self._push_alerts()
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
        # Columns that exist in the Supabase events table
        EVENTS_ALLOWED_KEYS = {
            "laptop_id", "event_type", "created_at",
            "state_before", "state_after", "rssi", "rssi_smooth",
            "image_url", "timestamp",
        }
        logger.debug("Pushing %d events to Supabase", len(rows))
        for row in rows:
            try:
                # Skip alert events that were accidentally stored in the events
                # table by older code — permanently mark them as errors so they
                # don't keep blocking the sync queue.
                if row["event_type"] == "ALERT_TELEGRAM":
                    self._queue.mark_error(
                        row["id"],
                        "ALERT_TELEGRAM rows belong in the alerts table (migrated)",
                        table="events",
                    )
                    # Mark as synced so they stop being retried
                    self._queue.mark_synced(row["id"], table="events")
                    continue

                # Strip any payload keys not present in the events table
                raw_payload = {k: v for k, v in row["payload"].items()
                               if k in EVENTS_ALLOWED_KEYS}
                payload = {
                    "laptop_id": self._laptop_id,
                    "event_type": row["event_type"],
                    "created_at": row["created_at"],
                    **raw_payload,
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

    async def _push_alerts(self) -> None:
        """Push unsynced alert records to Supabase alerts table."""
        if not self._client or not self._laptop_id:
            return
        rows = self._queue.get_unsynced(table="alerts")
        if not rows:
            return
        for row in rows:
            try:
                p = row["payload"]
                payload = {
                    "laptop_id": self._laptop_id,
                    "event_type": row["event_type"],
                    "alert_type": p.get("alert_type"),
                    "original_event": p.get("original_event"),
                    "success": p.get("success"),
                    "error": p.get("error"),
                    "created_at": row["created_at"],
                }
                self._client.table("alerts").insert(payload).execute()
                self._queue.mark_synced(row["id"], table="alerts")
            except Exception as exc:
                logger.warning("Failed to push alert %d: %s", row["id"], exc)
                self._queue.mark_error(row["id"], str(exc), table="alerts")



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

                # Also update laptops with latest metrics in Supabase directly
                if self._authenticated and self._client and self._laptop_id:
                    try:
                        self._client.table("laptops").update({
                            "last_seen": datetime.now(timezone.utc).isoformat(),
                            "battery_percent": snapshot.get("battery_percent"),
                            "charging": snapshot.get("charging"),
                            "network_online": snapshot.get("network_online"),
                            "security_mode": self._monitor.state.name,
                            "location": snapshot.get("location"),
                            "storage_total_gb": snapshot.get("storage_total_gb"),
                            "storage_used_gb": snapshot.get("storage_used_gb"),
                            "storage_free_gb": snapshot.get("storage_free_gb"),
                            "storage_usage_pct": snapshot.get("storage_usage_pct"),
                            "ram_total_gb": snapshot.get("ram_total_gb"),
                            "ram_used_gb": snapshot.get("ram_used_gb"),
                            "ram_usage_pct": snapshot.get("ram_usage_pct"),
                            "cpu_model": snapshot.get("cpu_model"),
                            "cpu_usage_pct": snapshot.get("cpu_percent"),
                            "gpu_model": snapshot.get("gpu_model"),
                            "gpu_vram_gb": snapshot.get("gpu_vram_gb"),
                            "gpu_usage_pct": snapshot.get("gpu_usage_pct"),
                            "display_info": snapshot.get("display_info"),
                            "system_specs": snapshot,
                        }).eq("id", self._laptop_id).execute()
                    except Exception as exc:
                        # Fallback to base columns if new schema is not yet applied
                        try:
                            self._client.table("laptops").update({
                                "last_seen": datetime.now(timezone.utc).isoformat(),
                                "battery_percent": snapshot.get("battery_percent"),
                                "network_online": snapshot.get("network_online"),
                                "security_mode": self._monitor.state.name,
                            }).eq("id", self._laptop_id).execute()
                        except Exception as exc2:
                            logger.debug("Heartbeat base update error: %s", exc2)

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
    # Webcam captures upload (security-images bucket)
    # ------------------------------------------------------------------

    async def upload_capture(self, photo: dict) -> Optional[str]:
        """
        Uploads a webcam photo to the 'security-images' Supabase Storage bucket.
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

        target_bucket = "security-images"
        public_url = None

        try:
            # Upload to security-images bucket
            storage_client = self._client.storage.from_(target_bucket)
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
                except Exception as exc_sub:
                    logger.debug("Security images upload fallback note: %s", exc_sub)

            public_url = storage_client.get_public_url(storage_path)

            # Upsert into captures table
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

            logger.info("Uploaded capture slot %d to %s bucket: %s", slot, target_bucket, storage_path)
            return public_url
        except Exception as exc:
            logger.warning("Failed to upload capture slot %d: %s", slot, exc)
            return None

    # ------------------------------------------------------------------
    # Location tracking & history synchronization
    # ------------------------------------------------------------------

    async def sync_location(
        self,
        sync_event: str = "PERIODIC_SYNC",
        image_url: Optional[str] = None,
    ) -> Optional[dict]:
        """
        Retrieves the physical laptop location and sends it to Supabase.
        Records location in 'locations' table (or 'heartbeats' as resilient fallback).
        Also associates with image_url if captured alongside webcam surveillance.
        Updates the laptop's latest location in 'laptops' table.
        Non-blocking, graceful error handling, does not fabricate fake coordinates.
        """
        try:
            from nodex.collector.location import get_current_location

            loc = await get_current_location(timeout=4.5)
            if not loc or loc.get("latitude") is None or loc.get("longitude") is None:
                logger.debug("Location sync skipped: no valid coordinates obtained")
                return None

            now_iso = datetime.now(timezone.utc).isoformat()
            loc_record = {
                "latitude": loc["latitude"],
                "longitude": loc["longitude"],
                "accuracy": loc.get("accuracy"),
                "altitude": loc.get("altitude"),
                "source": loc.get("source", "unknown"),
                "city": loc.get("city"),
                "region": loc.get("region"),
                "country": loc.get("country"),
                "country_code": loc.get("country_code"),
                "ip": loc.get("ip"),
                "sync_event": sync_event,
                "image_url": image_url,
                "metadata": {
                    "security_mode": self._monitor.state.name,
                    "mock_ble": settings.mock_ble,
                    "ble_connected": self._monitor._ble.connected,
                    "display_name": loc.get("display_name"),
                },
                "timestamp": loc.get("timestamp") or now_iso,
            }

            # Enqueue locally for offline trail
            try:
                self._queue.enqueue_heartbeat({
                    "event_type": f"LOC_{sync_event}",
                    "security_mode": self._monitor.state.name,
                    "location": loc_record,
                    "created_at": now_iso,
                })
            except Exception as q_err:
                logger.debug("Local queue location enqueue note: %s", q_err)

            # Ensure Supabase authenticated
            ok = await self._ensure_auth()
            if not ok or not self._client or not self._laptop_id:
                logger.debug("Location enqueued locally (Supabase unauthenticated/offline)")
                return loc_record

            # 1. Attempt insert into dedicated 'locations' table
            location_saved = False
            try:
                loc_payload = {
                    "laptop_id": self._laptop_id,
                    "created_at": now_iso,
                    **loc_record,
                }
                res = self._client.table("locations").insert(loc_payload).execute()
                if res.data:
                    location_saved = True
                    logger.info("Location record persisted to Supabase locations table (%s)", sync_event)
            except Exception as loc_tbl_err:
                logger.debug("locations table insert note: %s — using heartbeats history fallback", loc_tbl_err)

            # 2. Resilient fallback: store in 'heartbeats' table so history is ALWAYS recorded
            if not location_saved:
                try:
                    hb_payload = {
                        "laptop_id": self._laptop_id,
                        "event_type": "LOCATION_SYNC",
                        "security_mode": self._monitor.state.name,
                        "location": loc_record,
                        "created_at": now_iso,
                    }
                    self._client.table("heartbeats").insert(hb_payload).execute()
                    logger.info("Location record persisted to Supabase heartbeats history (%s)", sync_event)
                except Exception as hb_err:
                    logger.warning("Failed to record location history to Supabase: %s", hb_err)

            # 3. Update 'laptops' table with latest location
            try:
                self._client.table("laptops").update({
                    "location": loc_record,
                    "last_seen": now_iso,
                }).eq("id", self._laptop_id).execute()
            except Exception as lap_err:
                logger.debug("Laptops table location update note: %s", lap_err)

            return loc_record

        except Exception as exc:
            logger.warning("sync_location encountered error: %s", exc)
            return None

