"""
Alert Engine for the Office Monitoring System.

Evaluates device state on every update and manages two types of alerts:

1. **After-hours alerts**: Fire when any device is ON outside office hours
   (before 9 AM or after 5 PM). Each alert is per-device.

2. **Room-idle alerts**: Fire when ALL devices in a room have been continuously
   ON for more than 2 hours. Checked 24/7, independent of office hours.

Alerts are automatically resolved when the triggering condition clears.
"""

from datetime import datetime, timedelta, timezone

from app.models import AlertRecord
from app.state_store import DeviceStateStore, ROOMS, BST, _room_to_snake


# Maximum number of recent alerts to retain (active + resolved)
MAX_RECENT_ALERTS = 100

# Threshold for room-idle alerts is now dynamic from store.settings


class AlertEngine:
    """
    Evaluates alert conditions against the current device state and
    maintains a list of active and recent (last 100) alert records.
    """

    def __init__(self) -> None:
        # Currently active alerts keyed by alert ID for fast lookup
        self._active: dict[str, AlertRecord] = {}

        # Recent alerts (active + resolved), most recent first, capped at 100
        self._recent: list[AlertRecord] = []

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def check_alerts(self, store: DeviceStateStore) -> None:
        """
        Run all alert checks against the current state.

        Called after every state mutation (simulator push, manual toggle).
        """
        self._check_after_hours(store)
        self._check_room_idle(store)

    def get_active_alerts(self) -> list[dict]:
        """Return all currently active alerts as serializable dicts."""
        return [alert.model_dump(mode="json") for alert in self._active.values()]

    def get_recent_alerts(self) -> list[dict]:
        """Return the last 100 alerts (active + resolved) as serializable dicts."""
        return [alert.model_dump(mode="json") for alert in self._recent]

    # ------------------------------------------------------------------
    # After-hours alert logic
    # ------------------------------------------------------------------

    def _check_after_hours(self, store: DeviceStateStore) -> None:
        """
        Check for devices that are ON outside office hours (before 9 AM
        or after 5 PM). Fires a per-device alert and resolves it when
        the device turns off or office hours resume.
        """
        now = datetime.now(BST)
        is_after_hours = store.is_after_hours(now)

        for device in store.devices.values():
            alert_id = f"after_hours_{device.id}"

            if is_after_hours and device.status == "on":
                # Condition active — create or keep alert
                if alert_id not in self._active:
                    alert = AlertRecord(
                        id=alert_id,
                        type="after_hours",
                        room=device.room,
                        device_id=device.id,
                        device_name=device.name,
                        message=(
                            f"{device.room} — {device.name} ({device.id}) "
                            f"is ON after office hours"
                        ),
                        timestamp=now,
                        active=True,
                    )
                    self._active[alert_id] = alert
                    self._push_recent(alert)
            else:
                # Condition cleared — resolve if previously active
                self._resolve(alert_id, now)

    # ------------------------------------------------------------------
    # Room-idle alert logic
    # ------------------------------------------------------------------

    def _check_room_idle(self, store: DeviceStateStore) -> None:
        """
        Check for rooms where ALL devices have been continuously ON for
        more than 2 hours. This check runs 24/7, independent of office hours.

        The continuous-on duration is the time since the LATEST device in
        the room turned on (i.e., the shortest continuous-on period among
        all devices). If that exceeds 2 hours, ALL devices have been on
        for at least that long.
        """
        now = datetime.now(BST)

        for room in ROOMS:
            alert_id = f"room_idle_{_room_to_snake(room)}"

            # Collect devices in this room
            room_devices = [
                d for d in store.devices.values() if d.room == room
            ]

            # Check if ALL devices are ON
            all_on = all(d.status == "on" for d in room_devices)

            if not all_on:
                # At least one device is off — resolve any existing alert
                self._resolve(alert_id, now)
                continue

            # All devices are ON — check continuous-on durations
            # We need the MINIMUM duration (the device that turned on most recently).
            # If even the most recently turned-on device has been on > 2 hours,
            # then all devices have been on for > 2 hours.
            min_duration = None
            for device in room_devices:
                duration = store.get_continuous_on_duration(device.id)
                if duration is None or duration == timedelta(0):
                    # Shouldn't happen since status is "on", but guard anyway
                    min_duration = timedelta(0)
                    break
                if min_duration is None or duration < min_duration:
                    min_duration = duration

            threshold = timedelta(hours=store.settings.room_idle_threshold_hours)
            if min_duration is not None and min_duration > threshold:
                # All devices have been on for > 2 hours — fire alert
                if alert_id not in self._active:
                    alert = AlertRecord(
                        id=alert_id,
                        type="room_idle",
                        room=room,
                        device_id=None,
                        device_name=None,
                        message=(
                            f"All devices in {room} have been continuously "
                            f"ON for more than {store.settings.room_idle_threshold_hours} hours"
                        ),
                        timestamp=now,
                        active=True,
                    )
                    self._active[alert_id] = alert
                    self._push_recent(alert)
            else:
                # Not yet over threshold — resolve if previously active
                self._resolve(alert_id, now)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve(self, alert_id: str, now: datetime) -> None:
        """Mark an alert as resolved if it is currently active."""
        if alert_id in self._active:
            resolved = self._active.pop(alert_id)
            # Update the record in the recent list to mark it resolved
            for i, rec in enumerate(self._recent):
                if rec.id == alert_id and rec.active:
                    self._recent[i] = rec.model_copy(
                        update={"active": False, "timestamp": now}
                    )
                    break

    def _push_recent(self, alert: AlertRecord) -> None:
        """Add an alert to the recent list, maintaining the cap."""
        self._recent.insert(0, alert)
        # Trim to MAX_RECENT_ALERTS
        if len(self._recent) > MAX_RECENT_ALERTS:
            self._recent = self._recent[:MAX_RECENT_ALERTS]
