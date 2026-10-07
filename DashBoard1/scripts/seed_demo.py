"""
NodeX — Demo Database Seeder
=============================
Populates your Supabase project with realistic dummy telemetry:
  - 1 Registered Laptop record
  - 5 Recent Device Heartbeats
  - 8 Realistic Proximity Security Events
  - 4 Webcam Intruder Captures (with synthesized preview images)
  - 2 Emergency Notification Alert Logs

Usage:
    python scripts/seed_demo.py
"""
import io
import os
import sys
import uuid
import socket
import platform
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add DashBoard1 to sys.path
_HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_HERE))

from supabase import create_client
from dotenv import load_dotenv
from PIL import Image, ImageDraw

load_dotenv(_HERE / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://cuykicctsaerrhquaeld.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN1eWtpY2N0c2FlcnJocXVhZWxkIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc5MTExOTU1NywiZXhwIjoyMTA2Njk1NTU3fQ.ItXnptfJ5gLWfDI-J-_EPEey-f1B1z4Z9ypTgof9WfQ")

client = create_client(SUPABASE_URL, SUPABASE_KEY)

def generate_sample_photo(slot: int, mode: str, ts: str) -> bytes:
    """Generate a clean dark diagnostic frame for the camera ring buffer."""
    img = Image.new("RGB", (640, 480), color=(17, 24, 39))
    draw = ImageDraw.Draw(img)
    draw.rectangle([15, 15, 625, 465], outline=(34, 211, 238), width=3)
    draw.text((40, 45), "NodeX Proximity Security", fill=(255, 255, 255))
    draw.text((40, 85), f"Surveillance Snapshot • Slot {slot}/20", fill=(34, 211, 238))
    draw.text((40, 125), f"Mode: {mode}", fill=(246, 173, 85))
    draw.text((40, 165), f"Timestamp: {ts}", fill=(148, 163, 184))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()

def seed_demo_data():
    print("[+] Connecting to Supabase...")
    now = datetime.now(timezone.utc)

    # 1. Collect live hardware telemetry
    from nodex.collector.system_info import collect_snapshot
    import asyncio
    snapshot = asyncio.run(collect_snapshot())

    hostname = socket.gethostname()
    fingerprint = f"demo-fp-{uuid.uuid4().hex[:12]}"
    print(f"[+] Seeding laptop record with full hardware telemetry for: {hostname}")

    laptop_row = {
        "fingerprint": fingerprint,
        "name": f"{hostname} (Active Station)",
        "os": snapshot["os"],
        "battery_percent": snapshot.get("battery_percent", 88.0),
        "charging": snapshot.get("charging", True),
        "network_online": snapshot.get("network_online", True),
        "security_mode": "ARMED",
        "last_seen": now.isoformat(),
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
        laptop_res = client.table("laptops").upsert(laptop_row, on_conflict="fingerprint").execute()
    except Exception as exc:
        # Fallback to base columns if extended schema is not yet applied
        print(f"[!] Full telemetry upsert note: {exc} — using base columns")
        base_row = {
            "fingerprint": fingerprint,
            "name": f"{hostname} (Active Station)",
            "os": snapshot["os"],
            "battery_percent": snapshot.get("battery_percent", 88.0),
            "network_online": True,
            "security_mode": "ARMED",
            "last_seen": now.isoformat(),
        }
        laptop_res = client.table("laptops").upsert(base_row, on_conflict="fingerprint").execute()

    if not laptop_res.data:
        print("[-] Failed to upsert laptop record")
        return

    laptop_id = laptop_res.data[0]["id"]
    print(f"[+] Laptop registered with UUID: {laptop_id}")

    # 2. Seed Heartbeats
    print("[+] Seeding device heartbeats with hardware telemetry...")
    heartbeats_data = []
    for i in range(5):
        hb_time = now - timedelta(minutes=(5 - i) * 2)
        heartbeats_data.append({
            "laptop_id": laptop_id,
            "event_type": "HEARTBEAT",
            "security_mode": "ARMED",
            "battery_percent": round(snapshot.get("battery_percent", 88.0) - (i * 0.5), 1),
            "charging": snapshot.get("charging", True),
            "network_online": True,
            "network_ip": snapshot.get("network_ip", "192.168.1.105"),
            "ble_connected": True,
            "rssi_smooth": -58.0 + (i * 1.5),
            "created_at": hb_time.isoformat(),
        })
    client.table("heartbeats").insert(heartbeats_data).execute()

    # 3. Seed Security Events
    print("[+] Seeding realistic security audit events...")
    events_timeline = [
        {"type": "ARM", "before": "DISARMED", "after": "ARMED", "rssi": -55.0, "smooth": -54.8, "delta_min": 45},
        {"type": "BLE_LOST", "before": "ARMED", "after": "BLE_LOST", "rssi": -88.0, "smooth": -84.2, "delta_min": 32},
        {"type": "GRACE_STARTED", "before": "BLE_LOST", "after": "GRACE_PERIOD", "rssi": -90.0, "smooth": -88.0, "delta_min": 31},
        {"type": "TOKEN_RECOVERED", "before": "GRACE_PERIOD", "after": "ARMED", "rssi": -52.0, "smooth": -53.5, "delta_min": 30},
        {"type": "MANUAL_TEST", "before": "ARMED", "after": "ARMED", "rssi": -56.0, "smooth": -55.0, "delta_min": 18},
        {"type": "BLE_LOST", "before": "ARMED", "after": "BLE_LOST", "rssi": -86.0, "smooth": -83.1, "delta_min": 10},
        {"type": "TOKEN_RECOVERED", "before": "GRACE_PERIOD", "after": "ARMED", "rssi": -51.0, "smooth": -52.4, "delta_min": 9},
        {"type": "SECURITY_EVENT", "before": "GRACE_PERIOD", "after": "LOCKED", "rssi": -92.0, "smooth": -91.0, "delta_min": 2},
    ]

    events_data = []
    for ev in events_timeline:
        ev_time = now - timedelta(minutes=ev["delta_min"])
        events_data.append({
            "laptop_id": laptop_id,
            "event_type": ev["type"],
            "state_before": ev["before"],
            "state_after": ev["after"],
            "rssi": ev["rssi"],
            "rssi_smooth": ev["smooth"],
            "created_at": ev_time.isoformat(),
            "timestamp": ev_time.isoformat(),
        })
    client.table("events").insert(events_data).execute()

    # 4. Seed Alerts
    print("[+] Seeding alert notification audit logs...")
    alerts_data = [
        {
            "laptop_id": laptop_id,
            "event_type": "SECURITY_EVENT",
            "alert_type": "telegram",
            "success": True,
            "error": None,
            "created_at": (now - timedelta(minutes=2)).isoformat(),
        },
        {
            "laptop_id": laptop_id,
            "event_type": "MANUAL_TEST",
            "alert_type": "telegram",
            "success": True,
            "error": None,
            "created_at": (now - timedelta(minutes=18)).isoformat(),
        },
    ]
    client.table("alerts").insert(alerts_data).execute()

    # 5. Seed Captures into 'security-images' and 'intruder-captures' buckets
    print("[+] Uploading 4 sample ring-buffer surveillance captures to security-images...")
    target_buckets = ["security-images", "intruder-captures"]

    for slot in range(1, 5):
        cap_time = (now - timedelta(minutes=slot * 4)).isoformat()
        mode = "LOCKED" if slot == 1 else "ARMED"
        img_bytes = generate_sample_photo(slot, mode, cap_time)
        storage_path = f"laptops/{laptop_id}/photo_{slot}.jpg"
        public_url = None

        for b_name in target_buckets:
            try:
                client.storage.from_(b_name).upload(
                    path=storage_path,
                    file=img_bytes,
                    file_options={"upsert": "true", "content-type": "image/jpeg"},
                )
            except Exception:
                try:
                    client.storage.from_(b_name).update(
                        path=storage_path,
                        file=img_bytes,
                        file_options={"content-type": "image/jpeg"},
                    )
                except Exception:
                    pass

        try:
            public_url = client.storage.from_("security-images").get_public_url(storage_path)
        except Exception:
            public_url = client.storage.from_("intruder-captures").get_public_url(storage_path)

        client.table("captures").upsert({
            "laptop_id": laptop_id,
            "slot": slot,
            "storage_path": storage_path,
            "image_url": public_url,
            "security_mode": mode,
            "captured_at": cap_time,
        }, on_conflict="laptop_id,slot").execute()

    print("\n[OK] SUCCESS: Demo data successfully seeded to Supabase!")
    print("    - 1 Laptop registered")
    print("    - 5 Heartbeats added")
    print("    - 8 Security Events added")
    print("    - 4 Captures uploaded to ring buffer")
    print("    - 2 Alerts logged")
    print("\nYou can now open Dashboard 2 (http://localhost:5173) to see all live telemetry!")

if __name__ == "__main__":
    seed_demo_data()
