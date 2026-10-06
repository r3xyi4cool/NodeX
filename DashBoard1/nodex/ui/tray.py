"""
NodeX System Tray
-----------------
Minimizes to the system tray instead of quitting.
Close button = minimize to tray.
Tray menu provides: Open Dashboard, Arm, Disarm, Quit (PIN required when ARMED).
"""
from __future__ import annotations

import asyncio
import logging
import webbrowser
from io import BytesIO
from typing import TYPE_CHECKING, Optional

from PIL import Image, ImageDraw
import pystray

from nodex.config.settings import settings
from nodex.monitor.state import SecurityState

if TYPE_CHECKING:
    from nodex.monitor.monitor import SecurityMonitor

logger = logging.getLogger(__name__)


def _make_icon(state: SecurityState) -> Image.Image:
    """Generate a 64×64 tray icon colored by security state."""
    color_map = {
        SecurityState.DISARMED:       "#4a5568",  # gray
        SecurityState.ARMED:          "#48bb78",  # green
        SecurityState.BLE_LOST:       "#ed8936",  # orange
        SecurityState.GRACE_PERIOD:   "#f6ad55",  # amber
        SecurityState.SECURITY_EVENT: "#fc8181",  # red-light
        SecurityState.RECOVERED:      "#68d391",  # light-green
        SecurityState.LOCKED:         "#e53e3e",  # red
    }
    color = color_map.get(state, "#4a5568")

    img = Image.new("RGB", (64, 64), color="#1a1a2e")
    draw = ImageDraw.Draw(img)
    # Outer ring
    draw.ellipse([4, 4, 60, 60], outline=color, width=4)
    # Inner filled circle
    draw.ellipse([16, 16, 48, 48], fill=color)
    return img


class TrayApp:
    """Wraps pystray to keep the app in the system tray."""

    def __init__(self, monitor: "SecurityMonitor", port: int) -> None:
        self._monitor = monitor
        self._port = port
        self._icon: Optional[pystray.Icon] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._quit_requested = False

    def setup(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._icon = pystray.Icon(
            "NodeX",
            icon=_make_icon(self._monitor.state),
            title="NodeX — Security Monitor",
            menu=self._build_menu(),
        )

    def _build_menu(self) -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem("Open Dashboard", self._open_dashboard, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Arm", self._arm),
            pystray.MenuItem("Disarm", self._disarm),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit NodeX", self._quit),
        )

    def update_icon(self, state: SecurityState) -> None:
        if self._icon:
            try:
                self._icon.icon = _make_icon(state)
                self._icon.title = f"NodeX — {state.label()}"
            except Exception:
                pass

    def run(self) -> None:
        """Run pystray (blocks the calling thread)."""
        if self._icon:
            self._icon.run()

    def stop(self) -> None:
        if self._icon:
            self._icon.stop()

    # ------------------------------------------------------------------
    # Tray menu actions
    # ------------------------------------------------------------------

    def _open_dashboard(self, icon, item) -> None:  # noqa: ARG002
        webbrowser.open(f"http://127.0.0.1:{self._port}")

    def _arm(self, icon, item) -> None:  # noqa: ARG002
        if self._loop:
            self._loop.call_soon_threadsafe(self._monitor.arm)

    def _disarm(self, icon, item) -> None:  # noqa: ARG002
        # Disarm from tray only works when no PIN is set (CLI-less safe default)
        if settings.arm_pin_hash:
            logger.warning("PIN required to disarm — use the dashboard")
            return
        if self._loop:
            self._loop.call_soon_threadsafe(self._monitor.disarm)

    def _quit(self, icon, item) -> None:  # noqa: ARG002
        state = self._monitor.state
        if state == SecurityState.ARMED:
            logger.warning("Cannot quit while ARMED without PIN — use dashboard")
            return
        logger.info("Quit requested from tray")
        self._quit_requested = True
        if self._loop:
            self._loop.call_soon_threadsafe(
                lambda: self._loop.stop()  # type: ignore[union-attr]
            )
        icon.stop()
