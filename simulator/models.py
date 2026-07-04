"""
models.py

Data models for the office simulator.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta


# Timezone offset for Bangladesh Standard Time (UTC+6)
BST = timezone(timedelta(hours=6))


@dataclass
class Device:
    """Represents a single device (fan or light) in the office."""

    id: str                # e.g. "drawing_room_fan_1"
    name: str              # e.g. "Fan 1"
    room: str              # e.g. "Drawing Room"
    device_type: str       # "fan" or "light"
    rated_power: int       # watts when ON (60 for fans, 15 for lights)

    status: str = "off"    # "on" or "off"

    last_changed: datetime = field(
        default_factory=lambda: datetime.now(BST)
    )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def power_watts(self) -> int:
        """Return actual power consumption: rated_power when ON, 0 when OFF."""
        return self.rated_power if self.status == "on" else 0

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """
        Return the standardized JSON representation expected by the backend.

        Shape:
        {
            "id": "drawing_room_light_1",
            "type": "light",
            "name": "Light 1",
            "room": "Drawing Room",
            "status": "on",
            "power_watts": 15,
            "last_changed": "2026-07-04T21:13:02+06:00"
        }
        """
        return {
            "id": self.id,
            "type": self.device_type,
            "name": self.name,
            "room": self.room,
            "status": self.status,
            "power_watts": self.power_watts,
            "last_changed": self.last_changed.isoformat(),
        }
