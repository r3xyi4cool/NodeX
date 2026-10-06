"""
NodeX Webcam Capture Module
---------------------------
Captures frames from the default webcam every 30 seconds when ARMED or LOCKED.
Implements a 20-photo circular ring buffer:
  - Slot 1 .. 20
  - When reaching 20, the next photo overwrites slot 1 locally and in Supabase Storage.
Runs OpenCV I/O in a background worker thread to never block the asyncio loop.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from nodex.config.settings import CAPTURES_DIR, settings

logger = logging.getLogger(__name__)


def _capture_sync(slot: int) -> Optional[dict]:
    """Synchronous webcam capture using OpenCV DirectShow (Windows)."""
    file_path = CAPTURES_DIR / f"photo_{slot}.jpg"

    try:
        import cv2

        # CAP_DSHOW is the fastest DirectShow backend on Windows
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not cap.isOpened():
            # Fallback to default backend
            cap = cv2.VideoCapture(0)

        if not cap.isOpened():
            logger.warning("Webcam not accessible — generating diagnostic test frame")
            return _generate_fallback_frame(slot, file_path)

        # Discard first 2 frames to allow camera auto-exposure to stabilize
        for _ in range(2):
            cap.read()

        ret, frame = cap.read()
        cap.release()

        if not ret or frame is None:
            logger.warning("Failed to grab webcam frame — generating fallback frame")
            return _generate_fallback_frame(slot, file_path)

        # Encode to JPEG with high quality
        success, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        if not success:
            logger.error("Failed to encode webcam frame to JPEG")
            return None

        jpeg_bytes = buffer.tobytes()
        file_path.write_bytes(jpeg_bytes)
        logger.info("Captured webcam photo slot %d -> %s (%d bytes)", slot, file_path.name, len(jpeg_bytes))

        return {
            "slot": slot,
            "filename": f"photo_{slot}.jpg",
            "local_path": str(file_path),
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "bytes": jpeg_bytes,
            "success": True,
        }

    except Exception as exc:
        logger.error("Webcam capture error: %s — falling back", exc)
        return _generate_fallback_frame(slot, file_path)


def _generate_fallback_frame(slot: int, file_path: Path) -> dict:
    """Generate a diagnostic placeholder image if camera hardware is unavailable or headless."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (640, 480), color=(26, 26, 46))
    draw = ImageDraw.Draw(img)
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    draw.rectangle([20, 20, 620, 460], outline=(237, 137, 54), width=3)
    draw.text((40, 50), "NodeX Proximity Security", fill=(255, 255, 255))
    draw.text((40, 90), f"Intruder Capture - Slot {slot}/20", fill=(246, 173, 85))
    draw.text((40, 130), f"Timestamp: {now_str}", fill=(160, 174, 192))
    draw.text((40, 170), "Status: Simulated / Camera Unavailable", fill=(252, 129, 129))

    import io
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    jpeg_bytes = buf.getvalue()
    file_path.write_bytes(jpeg_bytes)

    return {
        "slot": slot,
        "filename": f"photo_{slot}.jpg",
        "local_path": str(file_path),
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "bytes": jpeg_bytes,
        "success": True,
    }


class CameraManager:
    """
    Manages periodic webcam capture and ring buffer rotation.
    """

    def __init__(self) -> None:
        self._last_capture: Optional[dict] = None
        self._total_captured = 0

    async def capture_next(self) -> Optional[dict]:
        """Advance ring slot (1..20) and capture a frame asynchronously."""
        if not settings.camera_enabled:
            return None

        slot = settings.next_photo_slot()
        result = await asyncio.to_thread(_capture_sync, slot)
        if result:
            self._last_capture = result
            self._total_captured += 1
        return result

    @property
    def last_capture(self) -> Optional[dict]:
        return self._last_capture

    @property
    def total_captured(self) -> int:
        return self._total_captured
