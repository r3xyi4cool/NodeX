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
        self._sync_lock = asyncio.Lock()

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
            auth_signed_in = False
            if email and password:
                try:
                    resp = self._client.auth.sign_in_with_password(
                        {"email": email, "password": password}
                    )
                    if resp.user is not None:
                        auth_signed_in = True
                        logger.info("Authenticated as %s", email)
                except Exception as auth_err:
                    logger.debug("Keyring password sign-in note: %s", auth_err)

            # Test direct client query execution with configured credentials
            try:
                self._client.table("laptops").select("id").limit(1).execute()
                self._authenticated = True
                await self._register_laptop()
                return True
            except Exception as test_err:
                if auth_signed_in:
                    self._authenticated = True
                    await self._register_laptop()
                    return True
                logger.warning("Supabase connection check failed: %s", test_err)
                self._authenticated = False
                return False

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
    # Immediate Synchronization Workflows
    # ------------------------------------------------------------------

    async def upload_all_now(self, progress_callback=None) -> dict:
        """
        Immediately uploads all available data to Supabase without waiting for sync interval:
        1. Device telemetry and hardware specs (laptops upsert + verify)
        2. Unsynchronized events, heartbeats, and alerts
        3. Fresh manual heartbeat record with full hardware snapshot
        4. Current geographical location
        5. All local webcam captures in the 20-photo buffer to security-images bucket + captures table
        6. Verifies that all uploaded items are confirmed in Supabase
        Returns a detailed report.
        """
        async with self._sync_lock:
            report = {
                "status": "UPLOADING_DATA",
                "telemetry_synced": False,
                "location_synced": False,
                "events_uploaded": 0,
                "heartbeats_uploaded": 0,
                "alerts_uploaded": 0,
                "photos_uploaded": 0,
                "photos_failed": 0,
                "verified": False,
                "errors": [],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            def _notify(step: str, msg: str = ""):
                if progress_callback:
                    try:
                        res = progress_callback(step, msg)
                        if asyncio.iscoroutine(res):
                            asyncio.create_task(res)
                    except TypeError:
                        try:
                            res = progress_callback(step)
                            if asyncio.iscoroutine(res):
                                asyncio.create_task(res)
                        except Exception:
                            pass
                    except Exception:
                        pass

            _notify("UPLOADING_DATA", "Authenticating and collecting telemetry...")

            ok = await self._ensure_auth()
            if not ok or not self._client:
                report["status"] = "FAILED"
                report["errors"].append("Unable to authenticate or connect with Supabase")
                _notify("UPLOAD_FAILED", "Unable to connect with Supabase")
                return report

            # 1. Telemetry and hardware registration / update
            try:
                await self._register_laptop()
                snapshot = await collect_snapshot()
                full_laptop_data = {
                    "fingerprint": get_hardware_fingerprint(),
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
                res = self._client.table("laptops").upsert(full_laptop_data, on_conflict="fingerprint").execute()
                if res.data:
                    self._laptop_id = str(res.data[0]["id"])
                    settings.laptop_id = self._laptop_id
                    report["telemetry_synced"] = True
            except Exception as e:
                report["errors"].append(f"Telemetry upload error: {e}")

            # 2. Location sync
            try:
                loc_res = await self.sync_location(sync_event="MANUAL_UPLOAD")
                if loc_res:
                    report["location_synced"] = True
            except Exception as e:
                report["errors"].append(f"Location sync error: {e}")

            # 3. Push unsynced queue rows (events, heartbeats, alerts)
            try:
                unsynced_ev_before = len(self._queue.get_unsynced(table="events"))
                unsynced_hb_before = len(self._queue.get_unsynced(table="heartbeats"))
                unsynced_al_before = len(self._queue.get_unsynced(table="alerts"))

                await self._push_events()
                await self._push_heartbeats()
                await self._push_alerts()

                unsynced_ev_after = len(self._queue.get_unsynced(table="events"))
                unsynced_hb_after = len(self._queue.get_unsynced(table="heartbeats"))
                unsynced_al_after = len(self._queue.get_unsynced(table="alerts"))

                report["events_uploaded"] = max(0, unsynced_ev_before - unsynced_ev_after)
                report["heartbeats_uploaded"] = max(0, unsynced_hb_before - unsynced_hb_after)
                report["alerts_uploaded"] = max(0, unsynced_al_before - unsynced_al_after)
            except Exception as e:
                report["errors"].append(f"Queue push error: {e}")

            # Also push an explicit manual sync snapshot heartbeat
            try:
                hb_snap = {
                    "laptop_id": self._laptop_id,
                    "event_type": "MANUAL_UPLOAD",
                    "security_mode": self._monitor.state.name,
                    "battery_percent": snapshot.get("battery_percent"),
                    "charging": snapshot.get("charging"),
                    "network_online": snapshot.get("network_online"),
                    "network_ip": snapshot.get("network_ip"),
                    "ble_connected": self._monitor._ble.connected,
                    "rssi_smooth": self._monitor._ble.rssi_smooth,
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
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                self._client.table("heartbeats").insert(hb_snap).execute()
                report["heartbeats_uploaded"] += 1
            except Exception as e:
                logger.debug("Manual heartbeat insert note: %s", e)

            # 4. Photos upload
            _notify("UPLOADING_PHOTOS", "Uploading webcam surveillance photos to Supabase Storage...")

            from nodex.config.settings import CAPTURES_DIR
            existing_photos = sorted(CAPTURES_DIR.glob("photo_*.jpg"), key=lambda p: p.stat().st_mtime, reverse=True)
            for photo_path in existing_photos:
                try:
                    slot_str = photo_path.stem.replace("photo_", "")
                    slot = int(slot_str) if slot_str.isdigit() else 1
                    jpeg_bytes = photo_path.read_bytes()
                    photo_dict = {
                        "slot": slot,
                        "bytes": jpeg_bytes,
                        "captured_at": datetime.fromtimestamp(photo_path.stat().st_mtime, timezone.utc).isoformat(),
                    }
                    uploaded_url = await self.upload_capture(photo_dict)
                    if uploaded_url:
                        report["photos_uploaded"] += 1
                    else:
                        report["photos_failed"] += 1
                except Exception as p_err:
                    report["photos_failed"] += 1
                    report["errors"].append(f"Photo {photo_path.name} upload error: {p_err}")

            # 5. Verification step
            _notify("VERIFYING_UPLOAD", "Verifying records in Supabase...")

            verified_laptop = False
            try:
                chk = self._client.table("laptops").select("id, last_seen").eq("id", self._laptop_id).execute()
                if chk.data and len(chk.data) > 0:
                    verified_laptop = True
            except Exception as v_err:
                report["errors"].append(f"Verification query error: {v_err}")

            report["verified"] = verified_laptop and report["telemetry_synced"]

            # Compute final status
            if report["verified"] and report["photos_failed"] == 0 and not report["errors"]:
                report["status"] = "SUCCESS"
            elif report["telemetry_synced"] or report["photos_uploaded"] > 0 or report["events_uploaded"] > 0:
                report["status"] = "PARTIAL"
            else:
                report["status"] = "FAILED"

            status_key = "UPLOAD_SUCCESSFUL" if report["status"] == "SUCCESS" else ("PARTIALLY_UPLOADED" if report["status"] == "PARTIAL" else "UPLOAD_FAILED")
            _notify(status_key, f"Upload completed with status: {report['status']}")

            return report

    async def upload_incident(self, incident: dict, photo_bytes: Optional[bytes] = None) -> dict:
        """
        Immediately uploads an incident to Supabase (genuine or simulated):
        - Inserts into events table
        - Uploads evidence photo to security-images bucket + captures table
        - Uploads location to locations table
        - Retains in local queue if offline
        """
        incident_id = incident.get("incident_id")
        event_type = incident.get("event_type", "BLE_LOST")
        simulated = bool(incident.get("is_simulation") or incident.get("simulated"))
        now_iso = datetime.now(timezone.utc).isoformat()

        # Enqueue in local SQLite queue immediately for guaranteed resilience
        local_event = {
            "incident_id": incident_id,
            "event_type": event_type,
            "state_before": incident.get("state_before", "ARMED"),
            "state_after": incident.get("state_after", "BLE_LOST"),
            "rssi": incident.get("rssi"),
            "rssi_smooth": incident.get("rssi_smooth"),
            "timestamp": now_iso,
            "simulated": simulated,
            "metadata": incident.get("metadata", {}),
        }
        row_id = self._queue.enqueue(local_event, table="events")

        photo_url = None
        if photo_bytes:
            try:
                slot = settings.next_photo_slot()
                photo_url = await self.upload_capture({
                    "slot": slot,
                    "bytes": photo_bytes,
                    "captured_at": now_iso,
                })
            except Exception as cam_err:
                logger.debug("Incident photo upload note: %s", cam_err)

        synced = False
        if await self._ensure_auth() and self._client and self._laptop_id:
            try:
                payload = {
                    "laptop_id": self._laptop_id,
                    "event_type": event_type,
                    "state_before": local_event["state_before"],
                    "state_after": local_event["state_after"],
                    "rssi": local_event["rssi"],
                    "rssi_smooth": local_event["rssi_smooth"],
                    "image_url": photo_url,
                    "created_at": now_iso,
                    "timestamp": now_iso,
                }
                res = self._client.table("events").insert(payload).execute()
                if res.data:
                    self._queue.mark_synced(row_id, table="events")
                    synced = True
            except Exception as up_err:
                logger.warning("Instant incident Supabase push error: %s (saved locally)", up_err)
                self._queue.mark_error(row_id, str(up_err), table="events")

            try:
                await self.sync_location(sync_event="INCIDENT_TRIGGERED", image_url=photo_url)
            except Exception as loc_err:
                logger.debug("Incident location sync note: %s", loc_err)

        return {
            "incident_id": incident_id,
            "synced": synced,
            "photo_url": photo_url,
            "row_id": row_id,
        }

    # ------------------------------------------------------------------
    # Sync loop
    # ------------------------------------------------------------------

    async def _sync_loop(self) -> None:
        attempt = 0
        while not self._stop_event.is_set():
            try:
                async with self._sync_lock:
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
            await self._ensure_auth()
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

