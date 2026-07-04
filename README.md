# Lights, Fans, Discord — Office Monitoring System

A real-time office monitoring system managing 15 simulated devices across 3 rooms. It features a backend source of truth, a live React dashboard, a standalone Python simulator, and a Discord bot for querying states.

## Architecture Overview

![Architecture Overview](assets/architecture.png)

- **Single Source of Truth**: The FastAPI backend maintains the full state of all devices, computes power and bills, and tracks continuous device usage.
- **Simulator**: Generates device events and pushes them to the backend. It polls the backend to respect "Automatic" or "Manual" mode.
- **Frontend Dashboard**: Subscribes to backend updates via Socket.IO for real-time changes without polling. Also issues REST commands when operating in manual mode.
- **Discord Bot**: Pulls real live data from the REST API to answer queries using Gemini AI for natural, conversational responses.

- Wokwi Link: `https://wokwi.com/projects/468551025532354561`
---

## Quick Start (One Click Setup)

### Prerequisites
Make sure you have the following installed on your computer:
- **[Git](https://git-scm.com/downloads)** — to download the project files
- **[Python 3.10+](https://www.python.org/downloads/)** — ⚠️ check **"Add python.exe to PATH"** during installation
- **[Node.js (LTS)](https://nodejs.org/)** — for the frontend dashboard and Discord bot

### Installation & Run
1. Download the **[`start_project.bat`](start_project.bat)** file.
2. Place it in any folder on your computer.
3. **Double-click** `start_project.bat`.

That's it! The script will automatically:
- Download the entire project from GitHub
- Set up all Python virtual environments and Node.js dependencies
- Download the required environment configuration files
- Ask if you'd like to invite the Discord Bot to your server
- Launch all 4 services (Backend, Simulator, Frontend, Discord Bot)
- Open the live dashboard in your default browser at `http://localhost:5173`
- It might take a few moments to install and run everything, please be patient and dont cut any window in the mean time.
- If discord bot is not working invite manually - `https://discord.com/oauth2/authorize?client_id=1522626157948964874&permissions=8&scope=bot%20applications.commands`

> **Running it again?** Just double-click the same file. It will detect everything is already set up and skip straight to launching the services.

---

## API Reference

### Real-time (Socket.IO)
- **Namespace**: `/`
- **Events Emitted by Server**:
  - `state_update`: `{ "devices": {...}, "mode": "automatic|manual" }`
  - `power_update`: `{ "total_watts": 0, "today_kwh": 0, "estimated_bill": 0, "rate_per_kwh": 8, "rooms": {...} }`
  - `alerts_update`: `{ "active": [...], "recent": [...] }`

### REST Endpoints
| Method | Route | Purpose | Example Payload |
|--------|-------|---------|--------------------|
| POST | `/api/simulator/push` | Bulk state update from simulator | `{ "devices": [ { "id": "...", "type": "light", "room": "...", "status": "on", "power_watts": 15, "last_changed": "..." } ] }` |
| GET | `/api/mode` | Get current mode | - |
| POST | `/api/mode` | Change mode (automatic/manual) | `{ "mode": "manual" }` |
| POST | `/api/devices/{device_id}` | Manually toggle device (Manual mode only) | `{ "status": "off" }` |
| GET | `/api/status` | Get all devices grouped by room | - |
| GET | `/api/status/{room}` | Get specific room status (supports aliases) | - |
| GET | `/api/power` | Get instant power draw | - |
| GET | `/api/usage` | Get kWh and billing estimate | - |
| GET | `/api/alerts` | Get active and recent alerts | - |

---

## Design Notes

### Modes (Automatic vs. Manual)
The system operates in one of two modes, strictly enforced by the backend:
- **Automatic**: The backend accepts bulk state pushes from the simulator (`/api/simulator/push`) and rejects manual device toggles (`/api/devices/{id}`). The frontend disables clickable toggles.
- **Manual**: The backend rejects simulator pushes and accepts manual device toggles. The simulator detects this by polling `/api/mode` and pauses its background loop.

### Alert Engine Logic
Alerts are evaluated continuously on every state mutation:
1. **After-hours Alert**: Active when **any** individual device is ON outside the `OFFICE_OPEN_HOUR` (9 AM) and `OFFICE_CLOSE_HOUR` (5 PM) window. This is a per-device alert.
2. **Room-idle Alert**: Active when **all** 5 devices in a single room have been continuously ON for more than 2 hours. This is checked 24/7, independent of office hours, by finding the minimum continuous-ON duration among the devices in the room.
