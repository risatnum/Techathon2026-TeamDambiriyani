# Lights, Fans, Discord — Office Monitoring System

A real-time office monitoring system managing 15 simulated devices across 3 rooms. It features a backend source of truth, a live React dashboard, a standalone Python simulator, and a Discord bot for querying states.

## Architecture Overview

```
[Python Simulator] --(HTTP POST / periodic push)--> [FastAPI Backend] <--REST/Socket.IO--> [Frontend Dashboard]
                                                             |
                                                             +--REST--> [Discord Bot (JS)]
```

- **Single Source of Truth**: The FastAPI backend maintains the full state of all devices, computes power and bills, and tracks continuous device usage.
- **Simulator**: Generates device events and pushes them to the backend. It polls the backend to respect "Automatic" or "Manual" mode.
- **Frontend Dashboard**: Subscribes to backend updates via Socket.IO for real-time changes without polling. Also issues REST commands when operating in manual mode.
- **Discord Bot**: Pulls real live data from the REST API to answer queries using Gemini AI for natural, conversational responses.

---

## Setup & Run Instructions

### 1. Backend (FastAPI)
The backend acts as the central hub.
```bash
cd backend
python -m venv venv
source venv/bin/activate  # (or venv\Scripts\activate on Windows)
pip install -r requirements.txt
uvicorn app.main:socket_app --host 0.0.0.0 --port 8000
```
**Environment Variables (`backend/.env`)**:
- `ELECTRICITY_RATE_PER_KWH` (Default: 8.0)
- `OFFICE_OPEN_HOUR` (Default: 9)
- `OFFICE_CLOSE_HOUR` (Default: 17)
- `CORS_ORIGINS` (Default: http://localhost:5173)

### 2. Simulator (Python)
Generates randomized device states and pushes them to the backend.
```bash
cd simulator
python -m venv venv
source venv/bin/activate  # (or venv\Scripts\activate on Windows)
pip install -r requirements.txt
python main.py
```
**Environment Variables (`simulator/.env`)**:
- `BACKEND_URL` (Default: http://localhost:8000)
- `PUSH_INTERVAL` (Default: 5)

### 3. Frontend Dashboard (React + Vite)
The live real-time dashboard.
```bash
cd frontend
npm install
npm run dev
```
It will start at `http://localhost:5173`. 

### 4. Discord Bot (Node.js)
Answers Discord commands using Gemini LLM and live backend data.
```bash
cd bot
npm install
npm start
```
**Environment Variables (`bot/.env`)**:
- `DISCORD_TOKEN`
- `GEMINI_API_KEY`
- `BACKEND_URL` (Default: http://localhost:8000)

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
|--------|-------|---------|-----------------|
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
