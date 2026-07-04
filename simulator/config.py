"""
config.py

Central configuration for the office simulator.
All constants and environment-variable overrides live here.
"""

import os

# ==============================
# ROOM DEFINITIONS
# ==============================

ROOMS = [
    "Drawing Room",
    "Work Room 1",
    "Work Room 2",
]

# ==============================
# DEVICE CONFIGURATION
# ==============================

DEVICE_CONFIG = {
    "fan": {
        "count": 2,
        "rated_power": 60,   # watts per fan
    },
    "light": {
        "count": 3,
        "rated_power": 15,   # watts per light
    },
}

# ==============================
# BACKEND CONNECTION
# ==============================

# Base URL of the backend API server.
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")

# ==============================
# TIMING
# ==============================

# Configurable push interval in seconds
PUSH_INTERVAL = int(os.environ.get("PUSH_INTERVAL", 5))

# How often (seconds) to re-check the backend mode when in manual mode.
MODE_CHECK_INTERVAL = 10
