"""
NodeX Dashboard 1 — Configuration Manager
Loads .env, manages nodex_config.json (runtime settings),
and provides a typed settings object to the whole application.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import socket
import subprocess
import uuid
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # DashBoard1/
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

ENV_FILE = BASE_DIR / ".env"
CONFIG_FILE = DATA_DIR / "nodex_config.json"
DB_FILE = DATA_DIR / "nodex_queue.db"
LOG_DIR = DATA_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
CAPTURES_DIR = DATA_DIR / "captures"
CAPTURES_DIR.mkdir(exist_ok=True)

load_dotenv(ENV_FILE)

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
_DEFAULTS: dict = {
    "grace_period_seconds": 15,
    "rssi_threshold": -75,
    "rssi_window_size": 5,
    "heartbeat_interval_seconds": 30,
    "ui_port": 7878,
    "enable_location": False,
    "paired_device_address": None,
    "paired_device_name": None,
    "paired_device_firmware": None,
    "laptop_id": None,          # set on first-run registration
    "arm_pin_hash": None,       # sha256 hex of the PIN
    "mock_ble": False,
    "telegram_chat_id": None,
    "camera_enabled": True,
    "camera_interval_seconds": 30,
    "camera_max_photos": 20,
    "camera_current_slot": 1,
}


class Settings:
    """
    Single source of truth for all runtime configuration.
    Backed by nodex_config.json; env vars are for secrets only.
    """

    def __init__(self) -> None:
        self._data: dict = dict(_DEFAULTS)
        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if CONFIG_FILE.exists():
            try:
                saved = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                self._data.update(saved)
            except (json.JSONDecodeError, OSError):
                pass  # corrupt file — start from defaults

    def save(self) -> None:
        CONFIG_FILE.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    # Typed accessors
    # ------------------------------------------------------------------

    @property
    def grace_period_seconds(self) -> int:
        return int(self._data["grace_period_seconds"])

    @grace_period_seconds.setter
    def grace_period_seconds(self, v: int) -> None:
        self._data["grace_period_seconds"] = max(5, int(v))
        self.save()

    @property
    def rssi_threshold(self) -> int:
        return int(self._data["rssi_threshold"])

    @rssi_threshold.setter
    def rssi_threshold(self, v: int) -> None:
        self._data["rssi_threshold"] = int(v)
        self.save()

    @property
    def rssi_window_size(self) -> int:
        return int(self._data["rssi_window_size"])

    @property
    def heartbeat_interval_seconds(self) -> int:
        return int(self._data["heartbeat_interval_seconds"])

    @property
    def ui_port(self) -> int:
        return int(self._data["ui_port"])

    @property
    def enable_location(self) -> bool:
        return bool(self._data["enable_location"])

    @enable_location.setter
    def enable_location(self, v: bool) -> None:
        self._data["enable_location"] = bool(v)
        self.save()

    @property
    def paired_device_address(self) -> Optional[str]:
        return self._data.get("paired_device_address")

    @paired_device_address.setter
    def paired_device_address(self, v: Optional[str]) -> None:
        self._data["paired_device_address"] = v
        self.save()

    @property
    def paired_device_name(self) -> Optional[str]:
        return self._data.get("paired_device_name")

    @paired_device_name.setter
    def paired_device_name(self, v: Optional[str]) -> None:
        self._data["paired_device_name"] = v
        self.save()

    @property
    def paired_device_firmware(self) -> Optional[str]:
        return self._data.get("paired_device_firmware")

    @paired_device_firmware.setter
    def paired_device_firmware(self, v: Optional[str]) -> None:
        self._data["paired_device_firmware"] = v
        self.save()

    @property
    def laptop_id(self) -> Optional[str]:
        return self._data.get("laptop_id")

    @laptop_id.setter
    def laptop_id(self, v: str) -> None:
        self._data["laptop_id"] = v
        self.save()

    @property
    def arm_pin_hash(self) -> Optional[str]:
        return self._data.get("arm_pin_hash")

    @arm_pin_hash.setter
    def arm_pin_hash(self, v: Optional[str]) -> None:
        self._data["arm_pin_hash"] = v
        self.save()

    @property
    def mock_ble(self) -> bool:
        return bool(self._data.get("mock_ble", False))

    @mock_ble.setter
    def mock_ble(self, v: bool) -> None:
        self._data["mock_ble"] = bool(v)
        self.save()

    @property
    def telegram_chat_id(self) -> Optional[str]:
        return self._data.get("telegram_chat_id")

    @telegram_chat_id.setter
    def telegram_chat_id(self, v: Optional[str]) -> None:
        self._data["telegram_chat_id"] = v
        self.save()

    @property
    def camera_enabled(self) -> bool:
        return bool(self._data.get("camera_enabled", True))

    @camera_enabled.setter
    def camera_enabled(self, v: bool) -> None:
        self._data["camera_enabled"] = bool(v)
        self.save()

    @property
    def camera_interval_seconds(self) -> int:
        return int(self._data.get("camera_interval_seconds", 30))

    @camera_interval_seconds.setter
    def camera_interval_seconds(self, v: int) -> None:
        self._data["camera_interval_seconds"] = max(5, int(v))
        self.save()

    @property
    def camera_max_photos(self) -> int:
        return int(self._data.get("camera_max_photos", 20))

    @property
    def camera_current_slot(self) -> int:
        return int(self._data.get("camera_current_slot", 1))

    @camera_current_slot.setter
    def camera_current_slot(self, v: int) -> None:
        self._data["camera_current_slot"] = int(v)
        self.save()

    def next_photo_slot(self) -> int:
        """
        Circular ring buffer (1 to camera_max_photos).
        When slot reaches 20, the next photo overwrites slot 1.
        """
        current = self.camera_current_slot
        next_slot = (current % self.camera_max_photos) + 1
        self.camera_current_slot = next_slot
        return current

    # ------------------------------------------------------------------
    # PIN helpers
    # ------------------------------------------------------------------

    def set_pin(self, raw_pin: str) -> None:
        """Hash and store a new PIN."""
        self.arm_pin_hash = hashlib.sha256(raw_pin.encode()).hexdigest()

    def verify_pin(self, raw_pin: str) -> bool:
        """Return True if raw_pin matches the stored hash."""
        if not self.arm_pin_hash:
            return True  # no PIN set → open
        return hashlib.sha256(raw_pin.encode()).hexdigest() == self.arm_pin_hash

    # ------------------------------------------------------------------
    # Secrets (from env / Credential Manager via keyring)
    # ------------------------------------------------------------------

    @property
    def supabase_url(self) -> str:
        return os.environ.get("SUPABASE_URL", "")

    @property
    def supabase_anon_key(self) -> str:
        return os.environ.get("SUPABASE_ANON_KEY", "")

    @property
    def nodex_user_email(self) -> str:
        return os.environ.get("NODEX_USER_EMAIL", "")

    @property
    def telegram_bot_token(self) -> str:
        return os.environ.get("TELEGRAM_BOT_TOKEN", "")


# ---------------------------------------------------------------------------
# Hardware fingerprint (stable identifier for this laptop)
# ---------------------------------------------------------------------------

def _get_win_machine_guid() -> str:
    """Read MachineGuid from the Windows registry (unique per OS install)."""
    try:
        out = subprocess.check_output(
            ["reg", "query",
             r"HKLM\SOFTWARE\Microsoft\Cryptography",
             "/v", "MachineGuid"],
            text=True, stderr=subprocess.DEVNULL,
        )
        for line in out.splitlines():
            if "MachineGuid" in line:
                return line.split()[-1]
    except Exception:
        pass
    return str(uuid.getnode())  # MAC-based fallback


def get_hardware_fingerprint() -> str:
    """Return a stable hex fingerprint for this laptop."""
    parts = [
        socket.gethostname(),
        platform.node(),
        _get_win_machine_guid(),
    ]
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()


# Singleton
settings = Settings()
