# Prompt for Google Antigravity — "Lights, Fans, Discord" Office Monitoring System

## CONTEXT

I'm building a hackathon project. The problem statement is: build a system where a simulated office (3 rooms, 18 devices total — 2 fans + 3 lights per room) is monitored through a **real-time web dashboard** and a **Discord bot**, both backed by a **single shared backend** (single source of truth).

I already have partial, unpolished code from three different people:

1. **A Python simulator** — generates dummy device data (status, power draw, room, last-changed timestamp) and writes/sends it as JSON. It's incomplete/rough and not fully wired to the backend.
2. **A FastAPI backend** — meant to receive the simulator's JSON and expose it via API, but the connection between simulator → backend is not finished, and there's no real-time push mechanism to the frontend yet.
3. **A Discord bot written in JavaScript** — has bot logic scaffolded but is not actually pulling live data from the backend (it's likely using stubs/hardcoded data right now).
4. **No frontend exists yet** — this needs to be built from scratch.

Your job is to **inspect the existing codebase, identify what's broken/missing/duplicated, and complete the system end-to-end** so it works as one cohesive, demo-ready application. Do not just patch — refactor where the existing code fights against a clean architecture.

---

## GOAL ARCHITECTURE (target end state)

```
[Python Simulator] --(HTTP POST / periodic push)--> [FastAPI Backend] <--REST/WebSocket--> [Frontend Dashboard]
                                                             |
                                                             +--REST--> [Discord Bot (JS)]
```

- **One source of truth**: the FastAPI backend holds the current state of all 18 devices in memory (a Python dict/object keyed by device ID), plus a rolling history buffer for usage-over-time and alert-duration tracking.
- The **simulator never talks directly to the frontend or the bot** — it only ever pushes to the backend.
- The **frontend and Discord bot both read exclusively from the backend API** — never from the simulator or from each other. This must be true even if it means adding endpoints that don't exist yet.
- **Alerts must be computed in the backend only**, not the simulator. If the simulator currently has any alert-detection logic, migrate that logic into the backend and strip it out of the simulator. The simulator's only job is to produce device state; the backend's job is to interpret that state.

---

## STEP 0 — AUDIT FIRST

Before writing new code:
1. Map out what currently exists in each of the three codebases (simulator, backend, Discord bot): list files, key functions/classes, and what each currently does vs. what it's supposed to do.
2. Identify overlapping responsibilities (e.g., alert logic duplicated in simulator and backend) and flag them for consolidation into the backend.
3. Identify any hardcoded/stubbed data in the Discord bot and flag it for replacement with real API calls.
4. Produce a short written summary of findings before touching code, so I can sanity-check the plan.

---

## STEP 1 — DATA MODEL (standardize this across simulator, backend, frontend, bot)

Each device object should look like:

```json
{
  "id": "drawing_room_light_1",
  "type": "light",
  "room": "drawing_room",
  "status": "on",
  "power_watts": 15,
  "last_changed": "2026-07-04T21:13:02+06:00"
}
```

Rooms: `drawing_room`, `work_room_1`, `work_room_2`. Each room: 3 lights (15W each when on) + 2 fans (60W each when on) = 5 devices, 18 total.

Standardize this schema across all three codebases. If the simulator's current JSON shape differs, adapt it (don't force the backend to adapt to an inconsistent shape — the simulator's output format is the thing that should conform, since the backend is the source of truth for the rest of the system).

---

## STEP 2 — SIMULATOR (polish, don't rebuild from scratch unless it's fundamentally broken)

1. Keep the simulator as a standalone Python module/script that generates and updates device states over time (random-walk style: occasionally flips a device, updates `last_changed`, assigns realistic wattage).
2. Instead of just writing a local JSON file, add an HTTP client that **pushes the current full device state to the backend** on an interval (e.g., every 3–5 seconds) via a `POST /api/simulator/push` endpoint (or similar — you decide the exact route, just document it).
3. Implement **two simulation modes**, controlled by the backend/frontend, not decided locally by the simulator:
   - **Automatic mode**: the simulator autonomously randomizes device states on its own schedule and keeps pushing updates.
   - **Manual mode**: the simulator pauses autonomous changes. Device state changes only happen when the backend tells it to (or, better: in manual mode, the backend itself becomes the sole state authority and the simulator simply stops pushing changes / only pushes on explicit request). Design this cleanly — see Step 3 for how mode-switching and manual overrides should be handled.
4. The simulator should expose (or accept) a way to query/set its current mode, so the backend can toggle it based on what the frontend requests.
5. Keep the JSON-file output too if useful for debugging/logging, but the **live system must run off the HTTP push to the backend**, not off reading a static file.

---

## STEP 3 — BACKEND (FastAPI) — this is the core of the work

### 3.1 State store
- Maintain the current state of all 18 devices in memory as the single source of truth (a dict keyed by device ID is fine — no database needed for this scope, but structure it behind a small service/repository class so it could be swapped for a DB later).
- Maintain a short rolling history per device (state changes with timestamps) — needed for the "on for more than 2 hours continuously" alert and for the "today's estimated kWh" calculation.

### 3.2 Ingestion
- Build/fix `POST /api/simulator/push` (or your chosen route) to accept the simulator's JSON payload and update the in-memory state store. Validate the payload (pydantic models) and reject malformed data gracefully.

### 3.3 Mode control (automatic vs manual)
- `GET /api/mode` and `POST /api/mode` (`{"mode": "automatic" | "manual"}`).
- When mode is **manual**, add an endpoint to directly set a device's state from the frontend, e.g. `POST /api/devices/{device_id}` with `{"status": "on" | "off"}`. This is how the manual radio button on the frontend actually does something — the user flips a device switch and the backend updates its own state store directly, ignoring/pausing simulator pushes while in manual mode.
- When mode is **automatic**, device-state endpoints should reject manual overrides (or the frontend should simply hide manual controls) and the backend should trust the simulator's periodic pushes.
- Persist the mode itself in the backend, and inform the simulator of mode changes if the simulator's own behavior needs to change (e.g., pause its autonomous loop while in manual mode).

### 3.4 Read/query API (used by both frontend and Discord bot)
- `GET /api/status` — full state of all 18 devices grouped by room.
- `GET /api/status/{room}` — status of one room.
- `GET /api/power` — total watts right now + per-room breakdown.
- `GET /api/usage` — today's estimated kWh so far (integrate power draw over time since midnight) and estimated cost (see 3.6).
- `GET /api/alerts` — current active alerts (see 3.5).

### 3.5 Alert logic (move entirely into the backend)
Implement these rules server-side, evaluated continuously (e.g., on every state update or on a scheduled tick):
- **After-hours alert**: any device still `on` outside office hours. Office hours = 9:00 AM–5:00 PM. Outside that window (5:00 PM–9:00 AM, spanning midnight) is when this alert type is active/checked.
- **Room-idle alert**: a room where *all* devices have been continuously `on` for more than 2 hours (use the rolling history/`last_changed` tracking to compute continuous-on duration).
- Each alert record should include: type, room/device affected, a human-readable message, a timestamp of when it was raised, and whether it's still active or has been resolved (state changed back to off).
- Store recent alerts (e.g., last N or last 24h) so the frontend can show a timestamped alert feed, not just a single current alert.
- Expose alerts via `GET /api/alerts` for the frontend, and make them queryable/pushable to the Discord bot too (see Step 4 bonus).

### 3.6 Power & billing math
- Total instantaneous watts = sum of `power_watts` for all devices with `status == "on"`.
- Today's kWh estimate = integral of total-watts-over-time since midnight, divided by 1000. A simple approximation (sum of watts × time-interval-in-hours across your polling/push interval) is fine for a hackathon — don't overengineer, but be explicit about the method in code comments/README.
- Estimated bill = kWh × a configurable rate (e.g., an env var `ELECTRICITY_RATE_PER_KWH`, default something reasonable like 8 BDT/kWh or your local currency — make this configurable, not hardcoded in multiple places).
- Expose both current watts, today's kWh, and estimated bill via `GET /api/usage`.

### 3.7 Real-time push to frontend
- Do **not** make the frontend poll on a dumb interval as the primary mechanism if you can help it — implement a **WebSocket** endpoint (e.g., `/ws/live`) that pushes the full status/power/alerts payload to connected clients whenever the state changes (on simulator push, on manual override, on alert trigger). This satisfies "must update in real time without a page refresh" properly.
- If WebSockets prove too time-constrained, a fallback of short-interval polling (e.g., every 2–3 seconds) via `GET /api/status` is acceptable, but WebSocket is strongly preferred and worth the extra effort here — implement it if at all feasible.
- Use FastAPI's native WebSocket support; keep a simple connection manager class to broadcast to all connected clients.

### 3.8 CORS & config
- Enable CORS for the frontend's origin.
- Pull configurable values (rate per kWh, office hours, ports, simulator push interval) from a `.env`/config module, not scattered magic numbers.

---

## STEP 4 — DISCORD BOT (JavaScript) — connect it to the real backend

1. Remove any hardcoded/stubbed/random response logic currently in the bot.
2. Implement an HTTP client (fetch/axios) inside the bot that calls the FastAPI backend's REST endpoints (`/api/status`, `/api/status/{room}`, `/api/power`, `/api/usage`, `/api/alerts`).
3. Implement the three required commands, all backed by real live data:
   - `!status` → pulls `GET /api/status`, formats a friendly per-room summary.
   - `!room <name>` → pulls `GET /api/status/{room}`, with sensible name matching (e.g., `work1`, `work_room_1`, `Work Room 1` should all resolve).
   - `!usage` → pulls `GET /api/usage`, reports current watts + today's kWh (and optionally the estimated bill).
4. Humanize responses. If an LLM API key is available, use an LLM call to turn the raw JSON into a friendly, varied sentence (not robotic). If no LLM is wired up yet, implement a solid template-based humanizer as a fallback, and structure the code so an LLM call can be dropped in later without a rewrite (a `formatResponse(data)` function that could call an LLM or use templates).
5. **Bonus (implement if time allows)**: subscribe the bot to alerts from the backend — either by polling `GET /api/alerts` every N seconds and diffing against previously-seen alerts, or (better) by having the backend call a webhook/endpoint on the bot when a new alert fires. When a new alert appears, post it proactively to a configured Discord channel ID, in the same friendly tone, e.g. "⚠️ Hey! Work Room 2 still has 2 fans and 3 lights ON and it's 10 PM. Did someone forget to leave?"
6. Keep Discord bot config (token, channel ID, backend base URL) in environment variables, not hardcoded.

---

## STEP 5 — FRONTEND (build from scratch)

No frontend exists yet — you're building this fresh. Choose a stack suited for fast real-time UI work (React is a safe default; Vite for fast setup). Connect to the backend's WebSocket (`/ws/live`) as primary data source, with REST fallback for initial load.

### Required sections/features:

1. **Live Device Status Panel**
   - All 18 devices, grouped by room, each clearly labeled ("Fan 1", "Light 3", etc.) with a visual on/off indicator.
   - Updates instantly via WebSocket push — no manual refresh.
   - (Bonus, time-permitting) a top-down office layout visualization where lights glow when on and fans visually animate when running — nice-to-have, not blocking for a working MVP.

2. **Simulation Mode Control**
   - Two radio buttons: **Automatic** and **Manual**.
   - Calls `POST /api/mode` when toggled.
   - In **Automatic** mode: device tiles are read-only/display-only, reflecting whatever the simulator pushes.
   - In **Manual** mode: device tiles become interactive toggles — clicking a device calls `POST /api/devices/{device_id}` to flip its state directly in the backend.
   - Clearly indicate the current active mode in the UI at all times.

3. **Power Consumption & Bill Section**
   - Live total wattage across the office.
   - Per-room wattage breakdown.
   - Today's estimated kWh usage.
   - Estimated bill (using the backend's configurable rate).
   - All values update live via WebSocket, no refresh needed.

4. **Active Alerts Panel**
   - Shows currently active alerts, each timestamped, pulled from `GET /api/alerts` / pushed via WebSocket.
   - Visually distinguish the two alert types (after-hours-on vs. room-idle-too-long).
   - Alert *checking* window in the UI/copy should reflect that after-hours means outside 9 AM–5 PM (i.e., active from 5 PM to 9 AM) — make sure the frontend's messaging/labels are consistent with the backend's actual logic rather than hardcoding a different window on the frontend.

5. General UX
   - Clean, readable, dashboard-style layout — sectioned clearly (status / power+bill / alerts / mode control). Doesn't need to be fancy, needs to be legible and clearly demo-able on camera.
   - Should gracefully handle backend disconnects (reconnect the WebSocket, show a "reconnecting" state rather than crashing).

---

## STEP 6 — GLUE / INTEGRATION CHECKLIST

Make sure, at the end, that this full loop actually works, and test it explicitly:

1. Simulator (automatic mode) pushes a device state change → backend updates state → frontend dashboard updates within ~1-3 seconds without refresh → alert panel/power numbers update accordingly.
2. Frontend switched to manual mode → toggling a device tile → backend state changes → same device state is reflected correctly if queried from Discord bot's `!status`/`!room` commands immediately after.
3. Leaving devices "on" past 5 PM (or simulate this with a manipulated/fast-forwarded clock for demo purposes if needed) → after-hours alert appears in both the dashboard alert panel and (bonus) gets proactively posted to Discord.
4. `!status`, `!room <name>`, `!usage` all return live, accurate, differently-phrased-each-time (if LLM-backed) answers matching what's on the dashboard at that moment.

---

## STEP 7 — DOCUMENTATION

Update/create a top-level `README.md` covering:
- Architecture overview (a text version of the diagram at the top of this prompt).
- Setup/run instructions for all three components (simulator, backend, frontend) plus the Discord bot, including required environment variables.
- API endpoint reference (route, method, purpose, example payload).
- Notes on the automatic/manual mode design and the alert logic, since these are the parts most likely to be asked about in evaluation/demo.

---

## GENERAL INSTRUCTIONS FOR YOU (Antigravity)

- Prefer fixing/refactoring the existing simulator, backend, and Discord bot code over rewriting from scratch, **except** where the existing code's structure actively works against the single-source-of-truth architecture above — in that case, refactor decisively rather than bolting on workarounds.
- Keep the codebase well-organized (clear folder structure per component: `/simulator`, `/backend`, `/bot`, `/frontend`) and well-commented, since code structure/documentation is part of the evaluation criteria.
- Favor a working, demoable MVP for all "minimum required" features first; treat the office-layout visualization and the LLM-humanized Discord responses as bonus polish once the core loop (simulator → backend → frontend + bot, live, both modes, alerts, billing) is solid and tested.
- Where you must make a judgment call not fully specified above (exact route names, exact JSON field names beyond what's specified, exact UI framework choices, exact alert-check interval), make a sensible decision and document it clearly rather than stopping to ask — but flag major architectural decisions in your summary so I can review them.
