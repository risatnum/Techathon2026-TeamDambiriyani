"""
api_client.py

Handles all HTTP communication with the backend.
The simulator uses this module to push device state and fetch the current mode.
"""

import requests

from config import BACKEND_URL


# ==============================
# PUSH FULL STATE
# ==============================

def push_full_state(devices: dict) -> None:
    """
    POST all 15 device states to the backend in a single request.

    Endpoint: POST /api/simulator/push
    Payload:  {"devices": [ ... device dicts ... ]}
    """
    payload = {
        "devices": [device.to_dict() for device in devices.values()]
    }

    try:
        response = requests.post(
            f"{BACKEND_URL}/api/simulator/push",
            json=payload,
            timeout=5,
        )

        if response.status_code == 200:
            print("[Backend] Full state pushed successfully.")
        else:
            print(f"[Backend] Push failed — HTTP {response.status_code}")

    except requests.exceptions.ConnectionError:
        # Backend might not be running yet; fail silently.
        print("[Backend Offline] Could not connect to backend.")
    except requests.exceptions.Timeout:
        print("[Backend Timeout] Request timed out.")
    except Exception as e:
        print(f"[Backend Error] {e}")


# ==============================
# FETCH MODE
# ==============================

def fetch_mode() -> str:
    """
    GET the current simulation mode from the backend.

    Endpoint: GET /api/mode
    Returns:  "automatic" or "manual"

    Falls back to "automatic" on any error.
    """
    try:
        response = requests.get(
            f"{BACKEND_URL}/api/mode",
            timeout=5,
        )

        if response.status_code == 200:
            data = response.json()
            return data.get("mode", "automatic")

        # Non-200 response — default to automatic
        return "automatic"

    except requests.exceptions.ConnectionError:
        print("[Backend Offline] Mode check failed — defaulting to automatic.")
        return "automatic"
    except requests.exceptions.Timeout:
        print("[Backend Timeout] Mode check timed out — defaulting to automatic.")
        return "automatic"
    except Exception as e:
        print(f"[Backend Error] {e} — defaulting to automatic.")
        return "automatic"
