"""
NodeX Alert System — Pluggable channel architecture
----------------------------------------------------
Base class defines the interface.
Telegram channel is implemented below.
Records each attempt in the local queue (alerts table).

To add a new channel (e.g. SMTP):
  1. Create alerts/email.py
  2. Subclass AlertChannel
  3. Instantiate in main.py alongside TelegramAlert

IMPORTANT: Bot token comes from .env (TELEGRAM_BOT_TOKEN).
           Chat ID is stored in config (telegram_chat_id).
"""
from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from nodex.config.settings import settings

if TYPE_CHECKING:
    from nodex.sync.queue import EventQueue

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class AlertChannel(ABC):
    """Abstract alert channel."""

    @abstractmethod
    async def send(self, event: dict) -> bool:
        """Send an alert for event. Return True on success."""
        ...


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------

class TelegramAlert(AlertChannel):
    """
    Sends a Telegram message when a security event occurs.
    Requires:
      TELEGRAM_BOT_TOKEN in .env
      telegram_chat_id in nodex_config.json (set via dashboard UI)
    """

    def __init__(self, queue: "EventQueue") -> None:
        self._queue = queue
        self._bot: Optional[object] = None
        self._init_bot()

    def _init_bot(self) -> None:
        token = settings.telegram_bot_token
        if not token:
            logger.warning(
                "TELEGRAM_BOT_TOKEN not set — Telegram alerts disabled"
            )
            return
        try:
            from telegram import Bot  # type: ignore
            self._bot = Bot(token=token)
            logger.info("Telegram bot initialised")
        except ImportError:
            logger.warning("python-telegram-bot not installed — Telegram alerts disabled")
        except Exception as exc:
            logger.warning("Telegram init error: %s", exc)

    async def send(self, event: dict) -> bool:
        if not self._bot:
            return False
        chat_id = settings.telegram_chat_id
        if not chat_id:
            logger.warning("Telegram chat_id not configured — skipping alert")
            return False

        event_type = event.get("event_type", "UNKNOWN")
        state = event.get("state_after", "?")
        rssi = event.get("rssi_smooth", "?")
        ts = event.get("timestamp", datetime.now(timezone.utc).isoformat())

        message = (
            f"🚨 *NodeX Security Alert*\n"
            f"Event: `{event_type}`\n"
            f"State: `{state}`\n"
            f"RSSI: `{rssi} dBm`\n"
            f"Time: `{ts}`\n"
            f"Laptop: `{settings.paired_device_name or 'unknown'}`"
        )

        success = False
        error_msg: Optional[str] = None
        try:
            await self._bot.send_message(  # type: ignore[union-attr]
                chat_id=chat_id,
                text=message,
                parse_mode="Markdown",
            )
            success = True
            logger.info("Telegram alert sent for %s", event_type)
        except Exception as exc:
            error_msg = str(exc)
            logger.warning("Telegram send failed: %s", exc)

        # Record in local queue (alerts table if exists, else events)
        self._queue.enqueue({
            "event_type": "ALERT_TELEGRAM",
            "alert_type": "telegram",
            "original_event": event_type,
            "success": success,
            "error": error_msg,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        return success


# ---------------------------------------------------------------------------
# Alert manager — routes events to all registered channels
# ---------------------------------------------------------------------------

class AlertManager:
    def __init__(self, queue: "EventQueue") -> None:
        self._channels: list[AlertChannel] = []
        self._queue = queue

    def register(self, channel: AlertChannel) -> None:
        self._channels.append(channel)
        logger.info("Alert channel registered: %s", type(channel).__name__)

    async def fire(self, event: dict) -> None:
        """Fire all channels asynchronously; never raise."""
        if not self._channels:
            return
        results = await asyncio.gather(
            *[ch.send(event) for ch in self._channels],
            return_exceptions=True,
        )
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                logger.warning("Alert channel %d error: %s", i, r)
