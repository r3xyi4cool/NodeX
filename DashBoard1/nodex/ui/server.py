"""
NodeX UI Server — FastAPI + WebSocket
Serves the dashboard HTML and provides real-time status via WebSocket.
Binds to 127.0.0.1 only (not exposed to LAN).
"""
from __future__ import annotations

import asyncio
import json
import logging
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from nodex.config.settings import settings, CAPTURES_DIR
from nodex.monitor.state import SecurityState

if TYPE_CHECKING:
    from nodex.ble.manager import BLEManager
    from nodex.monitor.monitor import SecurityMonitor
    from nodex.sync.queue import EventQueue
    from nodex.alerts.alerts import AlertManager

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(exist_ok=True)


class NodeXUIServer:
    """
    Hosts the local web dashboard on 127.0.0.1:PORT.
    Broadcasts live status to all connected WebSocket clients.
    """

    def __init__(
        self,
        ble: "BLEManager",
        monitor: "SecurityMonitor",
        queue: "EventQueue",
        alert_manager: "AlertManager",
        camera: Optional[object] = None,
    ) -> None:
        self._ble = ble
        self._monitor = monitor
        self._queue = queue
        self._alert_manager = alert_manager
        self._camera = camera
        self._ws_clients: Set[WebSocket] = set()
        self._server: Optional[uvicorn.Server] = None
        self.app = self._build_app()

        # Wire monitor broadcasts to WebSocket
        self._monitor.on_state_change = self._on_status_update

    # ------------------------------------------------------------------
    # FastAPI app
    # ------------------------------------------------------------------

    def _build_app(self) -> FastAPI:
        app = FastAPI(title="NodeX Dashboard 1", docs_url=None, redoc_url=None)

        # Mount static files
        if STATIC_DIR.exists():
            app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

        # Mount local captures folder for live preview
        if CAPTURES_DIR.exists():
            app.mount("/captures", StaticFiles(directory=str(CAPTURES_DIR)), name="captures")

        # ---- Routes ----

        @app.get("/", response_class=HTMLResponse)
        async def dashboard():
            html_file = STATIC_DIR / "index.html"
            if html_file.exists():
                return HTMLResponse(html_file.read_text(encoding="utf-8"))
            return HTMLResponse("<h1>NodeX</h1><p>Static files not found.</p>")

        # -- WebSocket --
        @app.websocket("/ws")
        async def websocket_endpoint(ws: WebSocket):
            await ws.accept()
            self._ws_clients.add(ws)
            logger.debug("WS client connected (total=%d)", len(self._ws_clients))
            try:
                # Send initial state on connect
                await ws.send_json(self._build_full_status())
                while True:
                    # Keep alive — process messages from client
                    data = await ws.receive_text()
                    await self._handle_ws_message(ws, json.loads(data))
            except WebSocketDisconnect:
                pass
            except Exception as exc:
                logger.debug("WS error: %s", exc)
            finally:
                self._ws_clients.discard(ws)
                logger.debug("WS client disconnected (total=%d)", len(self._ws_clients))

        # -- REST API endpoints --

        @app.get("/api/status")
        async def api_status():
            return JSONResponse(self._build_full_status())

        @app.post("/api/arm")
        async def api_arm(body: dict = {}):
            pin = body.get("pin", "")
            if not settings.verify_pin(pin):
                raise HTTPException(status_code=403, detail="Invalid PIN")
            self._monitor.arm()
            return {"ok": True, "state": self._monitor.state.name}

        @app.post("/api/disarm")
        async def api_disarm(body: dict = {}):
            pin = body.get("pin", "")
            if not settings.verify_pin(pin):
                raise HTTPException(status_code=403, detail="Invalid PIN")
            self._monitor.disarm()
            return {"ok": True, "state": self._monitor.state.name}

        @app.post("/api/test")
        async def api_test(body: dict = {}):
            pin = body.get("pin", "")
            if not settings.verify_pin(pin):
                raise HTTPException(status_code=403, detail="Invalid PIN")
            self._monitor.manual_test()
            return {"ok": True}

        @app.post("/api/pair/scan")
        async def api_scan():
            devices = await self._ble.scan(duration=8.0)
            return {"devices": devices}

        @app.post("/api/pair/select")
        async def api_pair(body: dict = {}):
            address = body.get("address")
            name = body.get("name", address)
            if not address:
                raise HTTPException(status_code=400, detail="address required")
            self._ble.pair(address, name)
            return {"ok": True, "address": address, "name": name}

        @app.post("/api/settings")
        async def api_settings(body: dict = {}):
            if "grace_period_seconds" in body:
                settings.grace_period_seconds = int(body["grace_period_seconds"])
            if "rssi_threshold" in body:
                settings.rssi_threshold = int(body["rssi_threshold"])
            if "enable_location" in body:
                settings.enable_location = bool(body["enable_location"])
            if "mock_ble" in body:
                settings.mock_ble = bool(body["mock_ble"])
            if "telegram_chat_id" in body:
                settings.telegram_chat_id = body["telegram_chat_id"]
            if "camera_enabled" in body:
                settings.camera_enabled = bool(body["camera_enabled"])
            if "camera_interval_seconds" in body:
                settings.camera_interval_seconds = int(body["camera_interval_seconds"])
            if "pin" in body:
                settings.set_pin(str(body["pin"]))
            return {"ok": True, "settings": self._get_settings_dict()}

        @app.get("/api/settings")
        async def api_get_settings():
            return JSONResponse(self._get_settings_dict())

        @app.get("/api/sync/status")
        async def api_sync_status():
            return JSONResponse(self._queue.status_dict())

        # -- Camera & Captures API --
        @app.get("/api/captures")
        async def api_get_captures():
            items = []
            for slot in range(1, settings.camera_max_photos + 1):
                f = CAPTURES_DIR / f"photo_{slot}.jpg"
                if f.exists():
                    stat = f.stat()
                    items.append({
                        "slot": slot,
                        "url": f"/captures/photo_{slot}.jpg",
                        "size": stat.st_size,
                        "updated_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                        "is_current": (slot == settings.camera_current_slot),
                    })
            return JSONResponse({
                "camera_enabled": settings.camera_enabled,
                "current_slot": settings.camera_current_slot,
                "max_photos": settings.camera_max_photos,
                "interval_seconds": settings.camera_interval_seconds,
                "captures": items,
            })

        @app.post("/api/captures/snap")
        async def api_snap_now():
            if self._camera and hasattr(self._camera, "capture_next"):
                photo = await self._camera.capture_next()
                if photo:
                    return {"ok": True, "slot": photo["slot"], "url": f"/captures/photo_{photo['slot']}.jpg"}
            return {"ok": False, "error": "Camera not available"}

        return app

    # ------------------------------------------------------------------
    # WebSocket helpers
    # ------------------------------------------------------------------

    async def _handle_ws_message(self, ws: WebSocket, msg: dict) -> None:
        """Handle incoming messages from the dashboard WebSocket client."""
        action = msg.get("action")
        pin = msg.get("pin", "")

        if action == "arm":
            if settings.verify_pin(pin):
                self._monitor.arm()
            else:
                await ws.send_json({"type": "error", "detail": "Invalid PIN"})

        elif action == "disarm":
            if settings.verify_pin(pin):
                self._monitor.disarm()
            else:
                await ws.send_json({"type": "error", "detail": "Invalid PIN"})

        elif action == "test":
            if settings.verify_pin(pin):
                self._monitor.manual_test()
            else:
                await ws.send_json({"type": "error", "detail": "Invalid PIN"})

        elif action == "ping":
            await ws.send_json({"type": "pong"})

    async def broadcast(self, data: dict) -> None:
        """Push data to all connected WebSocket clients."""
        if not self._ws_clients:
            return
        dead: Set[WebSocket] = set()
        for ws in list(self._ws_clients):
            try:
                await ws.send_json(data)
            except Exception:
                dead.add(ws)
        self._ws_clients -= dead

    def _on_status_update(self, status: dict) -> None:
        """Called by monitor on every state change — bridge to async broadcast."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self.broadcast(status))
        except RuntimeError:
            pass

    # ------------------------------------------------------------------
    # Data builders
    # ------------------------------------------------------------------

    def _build_full_status(self) -> dict:
        return {
            "type": "full_status",
            "state": self._monitor.state.name,
            "state_label": self._monitor.state.label(),
            "state_css": self._monitor.state.css_class(),
            "ble_connected": self._ble.connected,
            "rssi": self._ble.rssi,
            "rssi_smooth": round(self._ble.rssi_smooth, 1) if self._ble.rssi_smooth else None,
            "grace_remaining": round(self._monitor.grace_remaining, 1),
            "paired_name": settings.paired_device_name,
            "paired_address": settings.paired_device_address,
            "firmware": self._ble.firmware_version,
            "esp32_battery": self._ble.device_battery,
            "grace_period": settings.grace_period_seconds,
            "rssi_threshold": settings.rssi_threshold,
            "sync": self._queue.status_dict(),
            "mock_ble": settings.mock_ble,
            "camera_enabled": settings.camera_enabled,
            "camera_current_slot": settings.camera_current_slot,
            "camera_max_photos": settings.camera_max_photos,
        }

    def _get_settings_dict(self) -> dict:
        return {
            "grace_period_seconds": settings.grace_period_seconds,
            "rssi_threshold": settings.rssi_threshold,
            "enable_location": settings.enable_location,
            "mock_ble": settings.mock_ble,
            "telegram_chat_id": settings.telegram_chat_id,
            "camera_enabled": settings.camera_enabled,
            "camera_interval_seconds": settings.camera_interval_seconds,
            "camera_max_photos": settings.camera_max_photos,
            "camera_current_slot": settings.camera_current_slot,
            "has_pin": settings.arm_pin_hash is not None,
            "ui_port": settings.ui_port,
        }

    # ------------------------------------------------------------------
    # Server lifecycle
    # ------------------------------------------------------------------

    async def start(self, open_browser: bool = True) -> None:
        """Start uvicorn in the background and optionally open browser."""
        port = settings.ui_port
        config = uvicorn.Config(
            self.app,
            host="127.0.0.1",
            port=port,
            log_level="warning",
            access_log=False,
        )
        self._server = uvicorn.Server(config)

        # Run uvicorn in a task (non-blocking)
        asyncio.create_task(self._server.serve(), name="uvicorn")
        logger.info("Dashboard UI at http://127.0.0.1:%d", port)

        if open_browser:
            await asyncio.sleep(0.5)  # give uvicorn a moment
            webbrowser.open(f"http://127.0.0.1:{port}")

    async def stop(self) -> None:
        if self._server:
            self._server.should_exit = True
