"""
Central configuration for the Office Monitoring System.

All values are loaded from environment variables (via .env file)
with sensible defaults. Override any value by setting the corresponding
environment variable or editing the .env file.
"""

import os
from dotenv import load_dotenv

# Load .env from the backend root directory
load_dotenv()

# ---------------------------------------------------------------------------
# Electricity billing rate in BDT per kWh.
# This is configurable — change via the ELECTRICITY_RATE_PER_KWH env var
# or in the .env file to match the local utility rate.
# ---------------------------------------------------------------------------
ELECTRICITY_RATE_PER_KWH: float = float(
    os.environ.get("ELECTRICITY_RATE_PER_KWH", "8.0")
)

# ---------------------------------------------------------------------------
# Office operating hours (used for after-hours alerts).
# Defaults: 9 AM to 5 PM. Devices left on outside this window trigger alerts.
# ---------------------------------------------------------------------------
OFFICE_OPEN_HOUR: int = int(os.environ.get("OFFICE_OPEN_HOUR", "9"))    # 9 AM
OFFICE_CLOSE_HOUR: int = int(os.environ.get("OFFICE_CLOSE_HOUR", "17"))  # 5 PM

# ---------------------------------------------------------------------------
# CORS origins allowed to connect to the API.
# Comma-separated list when provided via env var.
# ---------------------------------------------------------------------------
_cors_raw = os.environ.get("CORS_ORIGINS", "http://localhost:5173")
CORS_ORIGINS: list[str] = [origin.strip() for origin in _cors_raw.split(",")]

# ---------------------------------------------------------------------------
# How often (in seconds) the simulator pushes device state to the backend.
# This is configurable — adjust to balance responsiveness vs. load.
# ---------------------------------------------------------------------------
SIMULATOR_PUSH_INTERVAL: int = int(
    os.environ.get("SIMULATOR_PUSH_INTERVAL", "5")
)
