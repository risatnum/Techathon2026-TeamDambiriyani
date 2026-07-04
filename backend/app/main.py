"""
FastAPI Application — Office Monitoring System Backend.

This is the main entry point. It wires together the FastAPI REST API,
the Socket.IO real-time server, the device state store, and the alert engine.

Run with:
    uvicorn app.main:socket_app --host 0.0.0.0 --port 8000
"""

import logging
import asyncio
from datetime import datetime

import socketio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import CORS_ORIGINS
from app.models import (
    DeviceToggleRequest,
    ModeRequest,
    SimulatorPushPayload,
    SystemSettings,
)
from app.state_store import DeviceStateStore
from app.alerts import AlertEngine
from app.socketio_manager import sio, broadcast_state_update

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Office Monitoring System API",
    description="Real-time office device monitoring, power tracking, and alerting.",
    version="1.0.0",
)

# CORS middleware — allow configured origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Module-level singletons
# ---------------------------------------------------------------------------
state_store = DeviceStateStore()
alert_engine = AlertEngine()

# ---------------------------------------------------------------------------
# Socket.IO ASGI app wrapping the FastAPI app.
# This is the ASGI app that should be served by uvicorn.
# ---------------------------------------------------------------------------
socket_app = socketio.ASGIApp(sio, other_asgi_app=app)

# ---------------------------------------------------------------------------
# Helper: broadcast after every state change
# ---------------------------------------------------------------------------

async def _broadcast() -> None:
    """Convenience wrapper to broadcast current state to all clients."""
    await broadcast_state_update(state_store, alert_engine)


async def background_alert_checker() -> None:
    """Continuously check alerts every 0.5s and lock mode if after hours."""
    from app.config import OFFICE_OPEN_HOUR, OFFICE_CLOSE_HOUR
    from app.state_store import BST
    
    last_alerts_hash = None
    last_mode = None
    last_after_hours = None

    while True:
        is_after_hours = state_store.is_after_hours()

        mode_changed = False

        alert_engine.check_alerts(state_store)

        # Determine if alerts changed
        active_alerts = alert_engine.get_active_alerts()
        alerts_hash = str([(a['id'], a['timestamp']) for a in active_alerts])
        current_mode = state_store.get_mode()

        if (alerts_hash != last_alerts_hash) or (current_mode != last_mode) or (is_after_hours != last_after_hours) or mode_changed:
            await _broadcast()
            last_alerts_hash = alerts_hash
            last_mode = current_mode
            last_after_hours = is_after_hours

        await asyncio.sleep(0.5)


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(background_alert_checker())


# ===================================================================
# API Routes
# ===================================================================

# ------------------------------------------------------------------
# Root
# ------------------------------------------------------------------

@app.get("/")
async def root():
    """Health-check / welcome endpoint."""
    return {"message": "Office Monitoring System API"}


# ------------------------------------------------------------------
# Simulator push endpoint
# ------------------------------------------------------------------

@app.post("/api/simulator/push")
async def simulator_push(payload: SimulatorPushPayload):
    """
    Receive a bulk device-state push from the simulator.

    Only accepted in 'automatic' mode. In 'manual' mode the simulator
    should not be pushing state, so we return 409 Conflict.
    
    If it is after office hours, the system ignores the updates so the
    state remains frozen.
    """
    if state_store.get_mode() == "manual":
        raise HTTPException(
            status_code=409,
            detail="Simulator push rejected: system is in manual mode",
        )

    if state_store.is_after_hours():
        # Ignore updates after hours so the state remains frozen
        return {"status": "ignored_after_hours"}

    state_store.update_all(payload.devices)
    alert_engine.check_alerts(state_store)
    await _broadcast()

    logger.info("Simulator push accepted: %d devices", len(payload.devices))
    return {"status": "ok"}


# ------------------------------------------------------------------
# Mode endpoints
# ------------------------------------------------------------------

@app.get("/api/mode")
async def get_mode():
    """Return the current operating mode."""
    return {"mode": state_store.get_mode(), "is_after_hours": state_store.is_after_hours()}


@app.post("/api/mode")
async def set_mode(request: ModeRequest):
    """
    Switch between 'automatic' and 'manual' mode.

    Broadcasts a state update so all clients reflect the new mode.
    """
    state_store.set_mode(request.mode)
    await _broadcast()

    logger.info("Mode changed to: %s", request.mode)
    return {"mode": request.mode, "status": "ok"}


# ------------------------------------------------------------------
# Settings endpoints
# ------------------------------------------------------------------

@app.get("/api/settings")
async def get_settings():
    """Return the current system settings."""
    return state_store.settings.model_dump(mode="json")


@app.post("/api/settings")
async def update_settings(settings: SystemSettings):
    """
    Update system settings (office hours, alert thresholds).
    """
    state_store.settings = settings
    alert_engine.check_alerts(state_store)
    await _broadcast()

    logger.info("Settings updated: %s", settings.model_dump_json())
    return {"status": "ok", "settings": settings.model_dump(mode="json")}


# ------------------------------------------------------------------
# Device toggle (manual mode only)
# ------------------------------------------------------------------

@app.post("/api/devices/{device_id}")
async def toggle_device(device_id: str, request: DeviceToggleRequest):
    """
    Toggle a single device ON or OFF.

    Only works in 'manual' mode — returns 403 in automatic mode.
    Returns 404 if the device_id is unknown.
    """
    if state_store.get_mode() != "manual":
        raise HTTPException(
            status_code=403,
            detail="Device toggle is only available in manual mode",
        )

    updated = state_store.update_device(device_id, request.status)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Device '{device_id}' not found")

    alert_engine.check_alerts(state_store)
    await _broadcast()

    logger.info("Device %s toggled to %s", device_id, request.status)
    return updated.model_dump(mode="json")


# ------------------------------------------------------------------
# Status endpoints
# ------------------------------------------------------------------

@app.get("/api/status")
async def get_status():
    """Return all 15 devices grouped by room."""
    return state_store.get_all_grouped()


@app.get("/api/status/{room}")
async def get_room_status(room: str):
    """
    Return devices for a specific room.

    Supports fuzzy room name matching:
    'work1', 'work_room_1', 'Work Room 1' all resolve to 'Work Room 1'.
    """
    devices = state_store.get_by_room(room)
    if devices is None:
        raise HTTPException(
            status_code=404,
            detail=f"Room '{room}' not found. Valid rooms: Drawing Room, Work Room 1, Work Room 2",
        )
    return devices


# ------------------------------------------------------------------
# Power & usage endpoints
# ------------------------------------------------------------------

@app.get("/api/power")
async def get_power():
    """Return current power draw summary by room."""
    return state_store.get_power_summary()


@app.get("/api/usage")
async def get_usage():
    """Return power usage summary with kWh, estimated bill, and rate."""
    return state_store.get_usage()


# ------------------------------------------------------------------
# Alerts endpoint
# ------------------------------------------------------------------

@app.get("/api/alerts")
async def get_alerts():
    """Return active and recent (last 100) alerts."""
    return {
        "active": alert_engine.get_active_alerts(),
        "recent": alert_engine.get_recent_alerts(),
    }
