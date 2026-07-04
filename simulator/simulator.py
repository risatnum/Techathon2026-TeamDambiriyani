"""
simulator.py

Core simulation engine for the office monitoring system.

- Creates 15 devices (2 fans + 3 lights per room × 3 rooms)
- Randomly toggles devices in automatic mode
- Pauses simulation when backend is in manual mode
- Pushes full device state to the backend after each toggle
"""

import random
import time
from datetime import datetime

from models import Device, BST
from config import ROOMS, DEVICE_CONFIG, PUSH_INTERVAL, MODE_CHECK_INTERVAL
from api_client import push_full_state, fetch_mode


class OfficeSimulator:
    """Simulates an office with fans and lights across multiple rooms."""

    def __init__(self):
        self.devices: dict[str, Device] = {}
        self.create_office()

    # ------------------------------------------------------------------
    # Device creation
    # ------------------------------------------------------------------

    def create_office(self) -> None:
        """Generate all 15 Device objects with proper snake_case IDs."""

        for room in ROOMS:

            # Convert room name to snake_case for device IDs
            room_key = room.lower().replace(" ", "_")

            # Create fans for this room
            for i in range(1, DEVICE_CONFIG["fan"]["count"] + 1):

                device_id = f"{room_key}_fan_{i}"

                self.devices[device_id] = Device(
                    id=device_id,
                    name=f"Fan {i}",
                    room=room,
                    device_type="fan",
                    rated_power=DEVICE_CONFIG["fan"]["rated_power"],
                )

            # Create lights for this room
            for i in range(1, DEVICE_CONFIG["light"]["count"] + 1):

                device_id = f"{room_key}_light_{i}"

                self.devices[device_id] = Device(
                    id=device_id,
                    name=f"Light {i}",
                    room=room,
                    device_type="light",
                    rated_power=DEVICE_CONFIG["light"]["rated_power"],
                )

        print(f"[Init] Created {len(self.devices)} devices across {len(ROOMS)} rooms.")

    # ------------------------------------------------------------------
    # Device toggling
    # ------------------------------------------------------------------

    def toggle_device(self, device_id: str) -> None:
        """Flip a device's status between 'on' and 'off'."""

        device = self.devices[device_id]

        # Toggle status
        device.status = "off" if device.status == "on" else "on"
        device.last_changed = datetime.now(BST)

        print(f"  {device.room} | {device.name} -> {device.status.upper()}")

    def random_toggle(self) -> None:
        """Pick a random device and toggle its state."""

        device_id = random.choice(list(self.devices.keys()))
        self.toggle_device(device_id)

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        """
        Main simulation loop. Runs 24/7 with no office-hours pause.

        1. Check backend mode (automatic / manual)
        2. If manual  → pause and re-check after MODE_CHECK_INTERVAL
        3. If automatic → toggle a random device, push state, sleep
        """

        while True:

            # Step 1: Ask the backend what mode we should be in
            mode = fetch_mode()

            # Step 2: Manual mode — do nothing, just wait and re-check
            if mode == "manual":
                print("Manual mode — pausing simulation")
                time.sleep(MODE_CHECK_INTERVAL)
                continue

            # Step 3: Automatic mode — simulate activity
            self.random_toggle()

            # Push full state (all 15 devices) to backend
            push_full_state(self.devices)

            # Sleep for a random interval between 3 and PUSH_INTERVAL+3 seconds
            wait_time = random.randint(3, PUSH_INTERVAL + 3)
            time.sleep(1)
