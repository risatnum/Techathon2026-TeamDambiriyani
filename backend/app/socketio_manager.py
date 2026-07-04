"""
Socket.IO Manager for the Office Monitoring System.

Provides real-time push of device state, power usage, and alerts to
connected frontend clients. Uses python-socketio AsyncServer with ASGI mode.
"""

import logging

import socketio

from app.state_store import DeviceStateStore
from app.alerts import AlertEngine

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Singleton Socket.IO async server
# ---------------------------------------------------------------------------
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",  # Allow all origins in development
    logger=False,
    engineio_logger=False,
)


# ---------------------------------------------------------------------------
# Connection lifecycle handlers
# ---------------------------------------------------------------------------

@sio.event
async def connect(sid: str, environ: dict) -> None:
    """Handle a new Socket.IO client connection."""
    logger.info("Socket.IO client connected: %s", sid)


@sio.event
async def disconnect(sid: str) -> None:
    """Handle a Socket.IO client disconnection."""
    logger.info("Socket.IO client disconnected: %s", sid)


# ---------------------------------------------------------------------------
# Broadcast helper
# ---------------------------------------------------------------------------

async def broadcast_state_update(
    state_store: DeviceStateStore,
    alert_engine: AlertEngine,
) -> None:
    """
    Broadcast the current system state to all connected clients.

    Emits three events:
      - `state_update`:  devices grouped by room + current mode
      - `power_update`:  power draw summary + kWh + billing
      - `alerts_update`: active and recent alerts
    """
    is_after_hours = state_store.is_after_hours()

    # 1. Device state grouped by room with current mode
    await sio.emit("state_update", {
        "devices": state_store.get_all_grouped(),
        "mode": state_store.get_mode(),
        "is_after_hours": is_after_hours,
    })

    # 2. Power and usage summary
    await sio.emit("power_update", state_store.get_usage())

    # 3. Alert state
    await sio.emit("alerts_update", {
        "active": alert_engine.get_active_alerts(),
        "recent": alert_engine.get_recent_alerts(),
    })
