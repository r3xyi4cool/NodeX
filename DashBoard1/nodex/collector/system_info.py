"""
NodeX Data Collector
---------------------
Collects system information (CPU, RAM, battery, network, location)
and packages it for heartbeats and event payloads.

Location is IP-based (ipapi.co), opt-in, city-level only, cached 5 min.
Fails gracefully — always returns None on any error.
"""
from __future__ import annotations

import asyncio
import logging
import platform
import socket
import time
from datetime import datetime, timezone
from typing import Optional

import psutil

from nodex.config.settings import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CPU brand (py-cpuinfo — slow first call, cached after)
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
    return _CPU_BRAND  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Location cache
# ---------------------------------------------------------------------------
_LOCATION_CACHE: Optional[dict] = None
_LOCATION_FETCHED_AT: float = 0.0
_LOCATION_TTL = 300.0  # 5 minutes


async def _fetch_location() -> Optional[dict]:
    """Fetch city-level location from ipapi.co.  Returns None on any failure."""
    global _LOCATION_CACHE, _LOCATION_FETCHED_AT

    if not settings.enable_location:
        return None

    now = time.monotonic()
    if _LOCATION_CACHE is not None and (now - _LOCATION_FETCHED_AT) < _LOCATION_TTL:
        return _LOCATION_CACHE

    try:
        import httpx

        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("https://ipapi.co/json/")
            resp.raise_for_status()
            data = resp.json()

        _LOCATION_CACHE = {
            "ip": data.get("ip"),
            "city": data.get("city"),
            "region": data.get("region"),
            "country": data.get("country_name"),
            "latitude": data.get("latitude"),
            "longitude": data.get("longitude"),
            "source": "ipapi.co",
        }
        _LOCATION_FETCHED_AT = now
        logger.debug("Location fetched: %s, %s", _LOCATION_CACHE["city"], _LOCATION_CACHE["country"])
        return _LOCATION_CACHE

    except Exception as exc:
        logger.warning("Location fetch failed (opt-in, continuing): %s", exc)
        return None


# ---------------------------------------------------------------------------
# Network status
# ---------------------------------------------------------------------------

def _get_network_status() -> dict:
    """Return IP, network name, and online flag."""
    try:
        # Best-effort: connect UDP to Google DNS to discover local IP
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
    except Exception:
        local_ip = "127.0.0.1"

    online = local_ip != "127.0.0.1"

    # Try to get SSID on Windows
    ssid: Optional[str] = None
    try:
        import subprocess
        result = subprocess.check_output(
            ["netsh", "wlan", "show", "interfaces"],
            text=True, stderr=subprocess.DEVNULL,
        )
        for line in result.splitlines():
            if "SSID" in line and "BSSID" not in line:
                ssid = line.split(":", 1)[-1].strip()
                break
    except Exception:
        pass

    return {"ip": local_ip, "online": online, "ssid": ssid}


# ---------------------------------------------------------------------------
# Battery
# ---------------------------------------------------------------------------

def _get_battery() -> dict:
    battery = psutil.sensors_battery()
    if battery is None:
        return {"percent": None, "charging": None, "available": False}
    return {
        "percent": round(battery.percent, 1),
        "charging": battery.power_plugged,
        "available": True,
    }


# ---------------------------------------------------------------------------
# Main collection function
# ---------------------------------------------------------------------------

async def collect_snapshot() -> dict:
    """
    Return a full system snapshot dict.
    Safe to call frequently — expensive ops (location, cpu_brand) are cached.
    """
    bat = _get_battery()
    net = _get_network_status()
    location = await _fetch_location()

    cpu_pct = psutil.cpu_percent(interval=None)
    ram = psutil.virtual_memory()

    return {
        "laptop_name": socket.gethostname(),
        "os": f"{platform.system()} {platform.version()}",
        "cpu_brand": _get_cpu_brand(),
        "cpu_percent": cpu_pct,
        "ram_total_gb": round(ram.total / (1024 ** 3), 2),
        "ram_percent": ram.percent,
        "battery_percent": bat["percent"],
        "charging": bat["charging"],
        "battery_available": bat["available"],
        "network_online": net["online"],
        "network_ip": net["ip"],
        "network_ssid": net.get("ssid"),
        "location": location,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
