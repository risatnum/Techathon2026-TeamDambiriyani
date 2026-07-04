"""
Pydantic models for the Office Monitoring System.

These models define the schema for device state, API requests/responses,
and alert records. They are shared across all backend components.
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class DeviceState(BaseModel):
    """
    Represents the current state of a single device (fan or light).

    - `status` is a string "on" or "off" (not boolean).
    - `power_watts` is the current draw: rated wattage when on, 0 when off.
    - `last_changed` is an ISO 8601 datetime with timezone info.
    """
    id: str
    type: Literal["fan", "light"]
    name: str
    room: str
    status: Literal["on", "off"]
    power_watts: int
    last_changed: datetime


class SimulatorPushPayload(BaseModel):
    """Payload sent by the simulator process with all device states."""
    devices: list[DeviceState]


class ModeRequest(BaseModel):
    """Request body for changing the operating mode."""
    mode: Literal["automatic", "manual"]


class DeviceToggleRequest(BaseModel):
    """Request body for toggling a single device on or off."""
    status: Literal["on", "off"]


class AlertRecord(BaseModel):
    """
    A single alert record — active or resolved.

    - `type`: "after_hours" for devices on outside office hours,
              "room_idle" for rooms with all devices continuously on > 2 hours.
    - `device_id` and `device_name` are set for after-hours alerts,
      but may be None for room-idle alerts.
    - `active`: True while the alert condition persists, False once resolved.
    """
    id: str
    type: Literal["after_hours", "room_idle"]
    room: str
    device_id: Optional[str] = None
    device_name: Optional[str] = None
    message: str
    timestamp: datetime
    active: bool = True


class SystemSettings(BaseModel):
    """
    Dynamic system settings for office hours and alerts.
    Times are stored in HH:MM format.
    """
    office_open_time: str = Field(default="09:00")
    office_close_time: str = Field(default="17:00")
    room_idle_threshold_hours: float = Field(default=2.0)
