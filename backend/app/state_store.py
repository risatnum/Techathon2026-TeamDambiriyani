"""
Device State Store — the single source of truth for all device state.

Maintains an in-memory dictionary of 15 devices (2 fans + 3 lights per room),
along with rolling history for continuous-on tracking and power samples for
kWh integration. All state mutations flow through this class.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from app.config import ELECTRICITY_RATE_PER_KWH
from app.models import DeviceState, SystemSettings

# UTC+6 timezone (Bangladesh Standard Time)
BST = timezone(timedelta(hours=6))

# ---------------------------------------------------------------------------
# Room and device definitions
# ---------------------------------------------------------------------------
ROOMS = ["Drawing Room", "Work Room 1", "Work Room 2"]

# Rated wattage per device type
WATTAGE = {"fan": 60, "light": 15}

# Device blueprint: (room, device_type, index)
DEVICE_BLUEPRINTS: list[tuple[str, str, int]] = []
for _room in ROOMS:
    for _i in range(1, 3):   # 2 fans per room
        DEVICE_BLUEPRINTS.append((_room, "fan", _i))
    for _i in range(1, 4):   # 3 lights per room
        DEVICE_BLUEPRINTS.append((_room, "light", _i))


def _room_to_snake(room: str) -> str:
    """Convert a Title Case room name to snake_case. e.g. 'Work Room 1' → 'work_room_1'."""
    return room.lower().replace(" ", "_")


def _make_device_id(room: str, device_type: str, index: int) -> str:
    """Build a device ID like 'drawing_room_fan_1'."""
    return f"{_room_to_snake(room)}_{device_type}_{index}"


def _make_device_name(device_type: str, index: int) -> str:
    """Build a human-readable device name like 'Fan 1' or 'Light 3'."""
    return f"{device_type.capitalize()} {index}"


# ---------------------------------------------------------------------------
# Fuzzy room name resolution
# ---------------------------------------------------------------------------
# Maps various shorthand / alternate forms to the canonical room name.
_ROOM_ALIASES: dict[str, str] = {}

for _room in ROOMS:
    snake = _room_to_snake(_room)
    # Canonical forms
    _ROOM_ALIASES[_room.lower()] = _room           # "work room 1"
    _ROOM_ALIASES[snake] = _room                    # "work_room_1"

    # Short aliases
    if "Drawing" in _room:
        _ROOM_ALIASES["drawing"] = _room
        _ROOM_ALIASES["drawing_room"] = _room
    elif "Work Room 1" == _room:
        _ROOM_ALIASES["work1"] = _room
        _ROOM_ALIASES["work_1"] = _room
        _ROOM_ALIASES["workroom1"] = _room
        _ROOM_ALIASES["work_room1"] = _room
    elif "Work Room 2" == _room:
        _ROOM_ALIASES["work2"] = _room
        _ROOM_ALIASES["work_2"] = _room
        _ROOM_ALIASES["workroom2"] = _room
        _ROOM_ALIASES["work_room2"] = _room


def resolve_room(name: str) -> Optional[str]:
    """
    Resolve a fuzzy room name to its canonical Title Case form.

    Supports: 'work1', 'work_room_1', 'Work Room 1', 'drawing', 'drawing_room', etc.
    Returns None if no match is found.
    """
    key = name.strip().lower().replace(" ", "_")
    # Try direct alias lookup first
    if key in _ROOM_ALIASES:
        return _ROOM_ALIASES[key]
    # Also try with spaces instead of underscores (handles "work room 1")
    key_spaces = key.replace("_", " ")
    if key_spaces in _ROOM_ALIASES:
        return _ROOM_ALIASES[key_spaces]
    return None


# ---------------------------------------------------------------------------
# DeviceStateStore
# ---------------------------------------------------------------------------

class DeviceStateStore:
    """
    In-memory store for all 15 device states.

    Provides methods for bulk updates (from the simulator), single-device
    toggling (manual mode), querying by room, power/usage summaries, and
    continuous-on duration tracking for alert evaluation.
    """

    def __init__(self) -> None:
        # Primary state: device_id → DeviceState
        self.devices: dict[str, DeviceState] = {}

        # Operating mode: "automatic" (simulator-driven) or "manual" (user-driven)
        self._mode: str = "automatic"

        # Rolling history per device: list of (status, timestamp) tuples.
        # Used to determine how long a device has been continuously ON.
        self._device_history: dict[str, list[tuple[str, datetime]]] = {}

        # Power history buffer: list of (timestamp, total_watts) samples.
        # Used for kWh integration via trapezoidal approximation.
        self._power_samples: list[tuple[datetime, float]] = []

        # Dynamic settings for office hours and alert thresholds
        self.settings = SystemSettings()

        # Initialize all 15 devices to OFF
        self.initialize_devices()

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def is_after_hours(self, now: Optional[datetime] = None) -> bool:
        """Check if the given time (or current time) is outside configured office hours."""
        if now is None:
            now = datetime.now(BST)
        open_time_dt = datetime.strptime(self.settings.office_open_time, "%H:%M").time()
        close_time_dt = datetime.strptime(self.settings.office_close_time, "%H:%M").time()
        current_time = now.time()

        if open_time_dt <= close_time_dt:
            return current_time < open_time_dt or current_time >= close_time_dt
        else:
            return current_time < open_time_dt and current_time >= close_time_dt

    def initialize_devices(self) -> None:
        """Create all 15 devices with default OFF state and zero power draw."""
        now = datetime.now(BST)

        for room, device_type, index in DEVICE_BLUEPRINTS:
            device_id = _make_device_id(room, device_type, index)
            self.devices[device_id] = DeviceState(
                id=device_id,
                type=device_type,
                name=_make_device_name(device_type, index),
                room=room,
                status="off",
                power_watts=0,
                last_changed=now,
            )
            # Start with an "off" history entry
            self._device_history[device_id] = [("off", now)]

        # Record initial power sample (0 W)
        self._add_power_sample()

    # ------------------------------------------------------------------
    # Bulk update (from simulator push)
    # ------------------------------------------------------------------

    def update_all(self, devices: list[DeviceState]) -> None:
        """
        Bulk-update device states from a simulator push.

        For each incoming device, record the state change in history
        (only when the status actually changed) and update the store.
        A new power sample is added after all devices are processed.
        """
        now = datetime.now(BST)

        for incoming in devices:
            device_id = incoming.id
            if device_id not in self.devices:
                continue  # Ignore unknown devices

            existing = self.devices[device_id]

            # Record state transition in history if status changed
            if existing.status != incoming.status:
                self._device_history.setdefault(device_id, []).append(
                    (incoming.status, now)
                )

            # Update the stored device state
            self.devices[device_id] = DeviceState(
                id=device_id,
                type=incoming.type,
                name=incoming.name,
                room=incoming.room,
                status=incoming.status,
                power_watts=incoming.power_watts,
                last_changed=incoming.last_changed,
            )

        # Record power sample after bulk update
        self._add_power_sample()

    # ------------------------------------------------------------------
    # Single-device update (manual mode toggle)
    # ------------------------------------------------------------------

    def update_device(self, device_id: str, status: str) -> Optional[DeviceState]:
        """
        Toggle a single device to the given status ('on' or 'off').

        Records the state change in history and updates power_watts
        based on the device type's rated wattage. Returns the updated
        DeviceState, or None if the device_id is unknown.
        """
        if device_id not in self.devices:
            return None

        now = datetime.now(BST)
        device = self.devices[device_id]

        # Determine power draw based on new status
        watts = WATTAGE.get(device.type, 0) if status == "on" else 0

        # Record state transition in history if status changed
        if device.status != status:
            self._device_history.setdefault(device_id, []).append(
                (status, now)
            )

        # Create updated device state
        updated = DeviceState(
            id=device_id,
            type=device.type,
            name=device.name,
            room=device.room,
            status=status,
            power_watts=watts,
            last_changed=now,
        )
        self.devices[device_id] = updated

        # Record power sample after update
        self._add_power_sample()

        return updated

    # ------------------------------------------------------------------
    # Query methods
    # ------------------------------------------------------------------

    def get_all_grouped(self) -> dict[str, list[dict]]:
        """Return all devices grouped by room name as serializable dicts."""
        grouped: dict[str, list[dict]] = {}
        for device in self.devices.values():
            room = device.room
            grouped.setdefault(room, []).append(device.model_dump(mode="json"))
        return grouped

    def get_by_room(self, room_query: str) -> Optional[list[dict]]:
        """
        Return devices for a specific room, supporting fuzzy matching.

        'work1', 'work_room_1', 'Work Room 1' all resolve to 'Work Room 1'.
        Returns None if the room cannot be resolved.
        """
        canonical = resolve_room(room_query)
        if canonical is None:
            return None

        return [
            device.model_dump(mode="json")
            for device in self.devices.values()
            if device.room == canonical
        ]

    # ------------------------------------------------------------------
    # Power & usage
    # ------------------------------------------------------------------

    def get_power_summary(self) -> dict:
        """
        Return current power draw summary.

        Returns: {total_watts, rooms: {room_name: watts}}
        """
        total = 0
        rooms: dict[str, int] = {}
        for device in self.devices.values():
            total += device.power_watts
            rooms[device.room] = rooms.get(device.room, 0) + device.power_watts
        return {"total_watts": total, "rooms": rooms}

    def get_usage(self) -> dict:
        """
        Return power usage summary including estimated kWh and billing.

        Returns: {total_watts, today_kwh, estimated_bill, rate_per_kwh, rooms: {room: watts}}
        """
        power = self.get_power_summary()
        today_kwh = self._calculate_today_kwh()
        estimated_bill = round(today_kwh * ELECTRICITY_RATE_PER_KWH, 2)

        return {
            "total_watts": power["total_watts"],
            "today_kwh": round(today_kwh, 4),
            "estimated_bill": estimated_bill,
            "rate_per_kwh": ELECTRICITY_RATE_PER_KWH,
            "rooms": power["rooms"],
        }

    # ------------------------------------------------------------------
    # Mode management
    # ------------------------------------------------------------------

    def get_mode(self) -> str:
        """Return the current operating mode ('automatic' or 'manual')."""
        return self._mode

    def set_mode(self, mode: str) -> None:
        """Set the operating mode to 'automatic' or 'manual'."""
        self._mode = mode

    # ------------------------------------------------------------------
    # Continuous-on duration tracking
    # ------------------------------------------------------------------

    def get_continuous_on_duration(self, device_id: str) -> Optional[timedelta]:
        """
        Return how long a device has been continuously ON.

        Walks the history backwards from the most recent entry. If the
        device is currently OFF, returns timedelta(0). Returns None if
        the device_id is unknown.
        """
        if device_id not in self.devices:
            return None

        device = self.devices[device_id]
        if device.status == "off":
            return timedelta(0)

        history = self._device_history.get(device_id, [])
        if not history:
            return timedelta(0)

        now = datetime.now(BST)

        # Walk backwards to find when the device last turned ON
        # (i.e., the most recent "on" entry that hasn't been followed by "off")
        on_since: Optional[datetime] = None
        for status, ts in reversed(history):
            if status == "on":
                on_since = ts
            elif status == "off":
                # The device was off before this point — stop
                break

        if on_since is None:
            return timedelta(0)

        return now - on_since

    # ------------------------------------------------------------------
    # Internal: power sample recording & kWh integration
    # ------------------------------------------------------------------

    def _add_power_sample(self) -> None:
        """Record a (timestamp, total_watts) sample for kWh calculation."""
        now = datetime.now(BST)
        total_watts = sum(d.power_watts for d in self.devices.values())
        self._power_samples.append((now, float(total_watts)))

    def _calculate_today_kwh(self) -> float:
        """
        Calculate energy consumed today (since midnight) using trapezoidal
        approximation over the recorded power samples.

        For each consecutive pair of samples (t1, w1) and (t2, w2):
            energy_wh += (w1 + w2) / 2 * (t2 - t1).total_seconds() / 3600

        Returns kWh (energy_wh / 1000).
        """
        now = datetime.now(BST)
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Filter to today's samples only
        today_samples = [
            (ts, watts) for ts, watts in self._power_samples
            if ts >= midnight
        ]

        if len(today_samples) < 2:
            # Not enough data points for integration — estimate from last sample
            if today_samples:
                _, watts = today_samples[-1]
                elapsed_hours = (now - midnight).total_seconds() / 3600
                # Simple estimate: current watts × time since midnight
                return (watts * elapsed_hours) / 1000
            return 0.0

        total_wh = 0.0
        for i in range(1, len(today_samples)):
            t1, w1 = today_samples[i - 1]
            t2, w2 = today_samples[i]
            delta_hours = (t2 - t1).total_seconds() / 3600
            # Trapezoidal rule: average of two readings × time interval
            total_wh += ((w1 + w2) / 2) * delta_hours

        return total_wh / 1000  # Convert Wh → kWh
