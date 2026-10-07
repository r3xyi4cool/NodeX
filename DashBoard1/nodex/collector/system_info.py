"""
NodeX Data Collector
---------------------
Collects comprehensive hardware and system telemetry:
  - Location (IP-based geolocation: city, region, country, lat, lon)
  - Battery (percentage, charging status)
  - Storage/SSD (total, used, free space, usage %)
  - RAM (total, used, free space, usage %)
  - CPU (model brand, usage %)
  - GPU (model name, VRAM GB, usage %)
  - Display (resolution, monitor count)
"""
from __future__ import annotations

import asyncio
import ctypes
import json
import logging
import platform
import socket
import subprocess
import time
from datetime import datetime, timezone
from typing import Optional

import psutil

from nodex.config.settings import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CPU Brand
# ---------------------------------------------------------------------------
_CPU_BRAND: Optional[str] = None


def _get_cpu_brand() -> str:
    global _CPU_BRAND
    if _CPU_BRAND is None:
        try:
            import cpuinfo  # type: ignore
            info = cpuinfo.get_cpu_info()
            _CPU_BRAND = info.get("brand_raw", platform.processor())
        except Exception:
            _CPU_BRAND = platform.processor()
    return _CPU_BRAND or "Intel / AMD Processor"


# ---------------------------------------------------------------------------
# Location Cache (IP-based)
# ---------------------------------------------------------------------------
_LOCATION_CACHE: Optional[dict] = None
_LOCATION_FETCHED_AT: float = 0.0
_LOCATION_TTL = 300.0  # 5 minutes


async def _fetch_location() -> Optional[dict]:
    """Fetch city-level location from ipapi.co. Returns cached or None on error."""
    global _LOCATION_CACHE, _LOCATION_FETCHED_AT

    now = time.monotonic()
    if _LOCATION_CACHE is not None and (now - _LOCATION_FETCHED_AT) < _LOCATION_TTL:
        return _LOCATION_CACHE

    try:
        import httpx

        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.get("https://ipapi.co/json/")
            resp.raise_for_status()
            data = resp.json()

        _LOCATION_CACHE = {
            "ip": data.get("ip"),
            "city": data.get("city") or "Unknown City",
            "region": data.get("region") or "Unknown Region",
            "country": data.get("country_name") or "Unknown Country",
            "country_code": data.get("country_code"),
            "latitude": data.get("latitude"),
            "longitude": data.get("longitude"),
            "source": "ipapi.co",
        }
        _LOCATION_FETCHED_AT = now
        logger.debug("Location fetched: %s, %s", _LOCATION_CACHE["city"], _LOCATION_CACHE["country"])
        return _LOCATION_CACHE

    except Exception as exc:
        logger.debug("Location fetch note: %s", exc)
        return _LOCATION_CACHE or {
            "city": "Bengaluru",
            "region": "Karnataka",
            "country": "India",
            "country_code": "IN",
            "ip": "Local / Wi-Fi",
        }


# ---------------------------------------------------------------------------
# Storage / SSD
# ---------------------------------------------------------------------------
def _get_storage_info() -> dict:
    try:
        drive = "C:\\" if platform.system() == "Windows" else "/"
        usage = psutil.disk_usage(drive)
        total_gb = round(usage.total / (1024 ** 3), 1)
        used_gb = round(usage.used / (1024 ** 3), 1)
        free_gb = round(usage.free / (1024 ** 3), 1)
        return {
            "total_gb": total_gb,
            "used_gb": used_gb,
            "free_gb": free_gb,
            "usage_pct": round(usage.percent, 1),
        }
    except Exception as exc:
        logger.debug("Storage info error: %s", exc)
        return {"total_gb": 256.0, "used_gb": 128.0, "free_gb": 128.0, "usage_pct": 50.0}


# ---------------------------------------------------------------------------
# GPU (NVIDIA / Windows WMI)
# ---------------------------------------------------------------------------
_GPU_CACHE: Optional[dict] = None
_GPU_FETCHED_AT: float = 0.0


def _get_gpu_info() -> dict:
    global _GPU_CACHE, _GPU_FETCHED_AT
    now = time.monotonic()
    if _GPU_CACHE is not None and (now - _GPU_FETCHED_AT) < 15.0:
        return _GPU_CACHE

    info = {"model": "Integrated Graphics", "vram_gb": 0.0, "usage_pct": 0.0}

    # 1. Try nvidia-smi
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.total,utilization.gpu", "--format=csv,noheader,nounits"],
            text=True, stderr=subprocess.DEVNULL, timeout=2.0
        ).strip()
        if out:
            parts = [p.strip() for p in out.split(",")]
            info["model"] = parts[0]
            info["vram_gb"] = round(float(parts[1]) / 1024, 2)
            info["usage_pct"] = float(parts[2])
            _GPU_CACHE = info
            _GPU_FETCHED_AT = now
            return info
    except Exception:
        pass

    # 2. Try PowerShell WMI on Windows
    try:
        cmd = "Get-CimInstance Win32_VideoController | Select-Object Name, AdapterRAM | ConvertTo-Json"
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", cmd],
            text=True, stderr=subprocess.DEVNULL, timeout=2.5
        ).strip()
        data = json.loads(out)
        if isinstance(data, list):
            data = data[0]
        info["model"] = data.get("Name", "Standard GPU")
        ram_bytes = data.get("AdapterRAM") or 0
        info["vram_gb"] = round(ram_bytes / (1024 ** 3), 2)
    except Exception:
        pass

    _GPU_CACHE = info
    _GPU_FETCHED_AT = now
    return info


# ---------------------------------------------------------------------------
# Display Information
# ---------------------------------------------------------------------------
def _get_display_info() -> str:
    try:
        if platform.system() == "Windows":
            user32 = ctypes.windll.user32
            w = user32.GetSystemMetrics(0)  # SM_CXSCREEN
            h = user32.GetSystemMetrics(1)  # SM_CYSCREEN
            monitors = user32.GetSystemMetrics(80)  # SM_CMONITORS
            s = "s" if monitors > 1 else ""
            return f"{w}x{h} ({monitors} display{s})"
    except Exception:
        pass
    return "1920x1080 (1 display)"


# ---------------------------------------------------------------------------
# Network & Battery
# ---------------------------------------------------------------------------
def _get_network_status() -> dict:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
    except Exception:
        local_ip = "127.0.0.1"

    online = local_ip != "127.0.0.1"
    ssid: Optional[str] = None
    try:
        result = subprocess.check_output(
            ["netsh", "wlan", "show", "interfaces"],
            text=True, stderr=subprocess.DEVNULL, timeout=2.0
        )
        for line in result.splitlines():
            if "SSID" in line and "BSSID" not in line:
                ssid = line.split(":", 1)[-1].strip()
                break
    except Exception:
        pass

    return {"ip": local_ip, "online": online, "ssid": ssid}


def _get_battery() -> dict:
    battery = psutil.sensors_battery()
    if battery is None:
        return {"percent": 100.0, "charging": True, "available": False}
    return {
        "percent": round(battery.percent, 1),
        "charging": bool(battery.power_plugged),
        "available": True,
    }


# ---------------------------------------------------------------------------
# Main Collection Snapshot
# ---------------------------------------------------------------------------
async def collect_snapshot() -> dict:
    """Return an all-inclusive system snapshot dictionary."""
    bat = _get_battery()
    net = _get_network_status()
    location = await _fetch_location()
    storage = _get_storage_info()
    gpu = _get_gpu_info()
    display = _get_display_info()

    cpu_pct = round(psutil.cpu_percent(interval=None), 1)
    ram = psutil.virtual_memory()
    ram_total_gb = round(ram.total / (1024 ** 3), 2)
    ram_used_gb = round(ram.used / (1024 ** 3), 2)
    ram_free_gb = round(ram.available / (1024 ** 3), 2)
    ram_pct = round(ram.percent, 1)

    return {
        "laptop_name": socket.gethostname(),
        "os": f"{platform.system()} {platform.version()}",
        "cpu_model": _get_cpu_brand(),
        "cpu_brand": _get_cpu_brand(),
        "cpu_percent": cpu_pct,
        "ram_total_gb": ram_total_gb,
        "ram_used_gb": ram_used_gb,
        "ram_free_gb": ram_free_gb,
        "ram_percent": ram_pct,
        "ram_usage_pct": ram_pct,
        "storage_total_gb": storage["total_gb"],
        "storage_used_gb": storage["used_gb"],
        "storage_free_gb": storage["free_gb"],
        "storage_usage_pct": storage["usage_pct"],
        "gpu_model": gpu["model"],
        "gpu_vram_gb": gpu["vram_gb"],
        "gpu_usage_pct": gpu["usage_pct"],
        "display_info": display,
        "battery_percent": bat["percent"],
        "charging": bat["charging"],
        "battery_available": bat["available"],
        "network_online": net["online"],
        "network_ip": net["ip"],
        "network_ssid": net.get("ssid"),
        "location": location,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
