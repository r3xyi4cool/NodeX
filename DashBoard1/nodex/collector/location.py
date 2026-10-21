"""
NodeX Laptop Location Provider
------------------------------
Retrieves the real geographical location of this laptop using:
1. Windows Native Geolocation (winrt.windows.devices.geolocation.Geolocator) as primary high-accuracy source.
2. OpenStreetMap (Nominatim) reverse-geocoding for city, region, and country metadata.
3. Network / IP-based geolocation fallback (ip-api.com / ipapi.co) if OS geolocation is unavailable.

Requirements:
- Never fabricates fake coordinates.
- Asynchronous and non-blocking with strict timeouts so the dashboard and telemetry collection never freeze.
- Works in Demo Mode and standard mode without requiring an ESP32 or BLE connection.
"""
from __future__ import annotations

import asyncio
import logging
import platform
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Cache the last reverse geocoding to avoid rate-limiting Nominatim
_LAST_REVERSE_KEY: Optional[str] = None
_LAST_REVERSE_DATA: Optional[dict] = None


async def _reverse_geocode_osm(lat: float, lon: float) -> dict:
    """Reverse geocode coordinates using OpenStreetMap Nominatim with caching."""
    global _LAST_REVERSE_KEY, _LAST_REVERSE_DATA
    # Round to ~100m to share reverse-geocode cache for small GPS drifts
    key = f"{round(lat, 3)},{round(lon, 3)}"
    if _LAST_REVERSE_KEY == key and _LAST_REVERSE_DATA:
        return _LAST_REVERSE_DATA

    try:
        import httpx

        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={"lat": lat, "lon": lon, "format": "json"},
                headers={"User-Agent": "NodeX-LocationTracker/1.0"},
            )
            if resp.status_code == 200:
                data = resp.json()
                addr = data.get("address", {})
                city = (
                    addr.get("city")
                    or addr.get("town")
                    or addr.get("municipality")
                    or addr.get("suburb")
                    or addr.get("county")
                )
                region = addr.get("state") or addr.get("region")
                country = addr.get("country")
                country_code = addr.get("country_code", "").upper() if addr.get("country_code") else None

                res = {
                    "city": city,
                    "region": region,
                    "country": country,
                    "country_code": country_code,
                    "display_name": data.get("display_name"),
                }
                _LAST_REVERSE_KEY = key
                _LAST_REVERSE_DATA = res
                return res
    except Exception as exc:
        logger.debug("OSM Nominatim reverse geocode note: %s", exc)

    return {}


async def _get_winrt_location(timeout: float = 4.0) -> Optional[dict]:
    """Retrieve position using Windows native Geolocator (WinRT)."""
    if platform.system() != "Windows":
        return None

    try:
        from winrt.windows.devices.geolocation import Geolocator

        async def _query():
            locator = Geolocator()
            pos = await locator.get_geoposition_async()
            coord = pos.coordinate
            point = coord.point.position
            return {
                "latitude": float(point.latitude),
                "longitude": float(point.longitude),
                "accuracy": float(coord.accuracy) if coord.accuracy is not None else None,
                "altitude": float(point.altitude) if point.altitude is not None else None,
                "source": "winrt",
            }

        res = await asyncio.wait_for(_query(), timeout=timeout)
        if res and res.get("latitude") is not None and res.get("longitude") is not None:
            # Enrich with OpenStreetMap reverse geocode
            geo = await _reverse_geocode_osm(res["latitude"], res["longitude"])
            res.update({
                "city": geo.get("city"),
                "region": geo.get("region"),
                "country": geo.get("country"),
                "country_code": geo.get("country_code"),
                "display_name": geo.get("display_name"),
            })
            return res
    except Exception as exc:
        logger.debug("WinRT geolocation note: %s", exc)

    return None


async def _get_ip_location(timeout: float = 3.5) -> Optional[dict]:
    """Retrieve location using IP geolocation services as fallback."""
    import httpx

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) NodeX-Client/1.0"}

    # 1. Try ip-api.com
    try:
        async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
            resp = await client.get("http://ip-api.com/json/")
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "success" and data.get("lat") is not None and data.get("lon") is not None:
                    return {
                        "latitude": float(data["lat"]),
                        "longitude": float(data["lon"]),
                        "accuracy": 5000.0,  # City-level accuracy approximation
                        "altitude": None,
                        "source": "ip-api",
                        "city": data.get("city"),
                        "region": data.get("regionName") or data.get("region"),
                        "country": data.get("country"),
                        "country_code": data.get("countryCode"),
                        "ip": data.get("query"),
                    }
    except Exception as exc:
        logger.debug("ip-api query note: %s", exc)

    # 2. Try ipapi.co (as demonstrated in TESTS/system.py)
    try:
        async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
            resp = await client.get("https://ipapi.co/json/")
            if resp.status_code == 200:
                data = resp.json()
                if data.get("latitude") is not None and data.get("longitude") is not None:
                    return {
                        "latitude": float(data["latitude"]),
                        "longitude": float(data["longitude"]),
                        "accuracy": 5000.0,
                        "altitude": None,
                        "source": "ipapi.co",
                        "city": data.get("city"),
                        "region": data.get("region"),
                        "country": data.get("country_name"),
                        "country_code": data.get("country_code"),
                        "ip": data.get("ip"),
                    }
    except Exception as exc:
        logger.debug("ipapi.co query note: %s", exc)

    return None


async def get_current_location(timeout: float = 5.0) -> Optional[dict]:
    """
    Acquire the latest physical laptop location.
    Prioritizes OS hardware geolocation (WinRT), then IP-based fallback.
    Returns None if all location attempts fail (does NOT fabricate fake coordinates).
    """
    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. Try OS native geolocation
    loc = await _get_winrt_location(timeout=min(timeout, 3.5))

    # 2. Try IP fallback if OS location failed or returned no coordinates
    if not loc or loc.get("latitude") is None or loc.get("longitude") is None:
        loc = await _get_ip_location(timeout=min(timeout, 3.0))

    if loc and loc.get("latitude") is not None and loc.get("longitude") is not None:
        loc["timestamp"] = now_iso
        return loc

    logger.warning("Could not determine current laptop location (OS and IP providers unavailable)")
    return None
