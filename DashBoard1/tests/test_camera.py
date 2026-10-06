"""
Unit tests for webcam capture and 20-photo circular buffer.
"""
import asyncio
from unittest.mock import MagicMock
import pytest

from nodex.config.settings import settings
from nodex.collector.camera import CameraManager, _generate_fallback_frame


def test_circular_ring_buffer():
    # Reset slot to 1
    settings.camera_current_slot = 1
    assert settings.camera_max_photos == 20

    # Advance 20 times (slots 1 to 20)
    slots = []
    for _ in range(20):
        s = settings.next_photo_slot()
        slots.append(s)

    assert slots == list(range(1, 21))

    # The 21st photo must wrap around to slot 1 (overwriting the first one)
    slot_21 = settings.next_photo_slot()
    assert slot_21 == 1

    # The 22nd photo must be slot 2
    slot_22 = settings.next_photo_slot()
    assert slot_22 == 2


def test_fallback_frame_generation(tmp_path):
    test_file = tmp_path / "photo_test.jpg"
    result = _generate_fallback_frame(slot=5, file_path=test_file)

    assert result["slot"] == 5
    assert result["filename"] == "photo_5.jpg"
    assert result["success"] is True
    assert len(result["bytes"]) > 0
    assert test_file.exists()


def test_camera_manager_capture():
    async def _run():
        mgr = CameraManager()
        # Ensure camera is enabled
        settings.camera_enabled = True
        result = await mgr.capture_next()

        assert result is not None
        assert 1 <= result["slot"] <= 20
        assert "bytes" in result
        assert result["success"] is True
        assert mgr.total_captured >= 1

    asyncio.run(_run())
