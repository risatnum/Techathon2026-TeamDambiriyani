require('dotenv').config();
const { Client, GatewayIntentBits } = require('discord.js');
const { GoogleGenerativeAI } = require('@google/generative-ai');

// =============================================================================
// Configuration
// =============================================================================

const DISCORD_TOKEN = process.env.DISCORD_TOKEN;
const GEMINI_API_KEY = process.env.GEMINI_API_KEY;
const BACKEND_URL = (process.env.BACKEND_URL || 'http://localhost:8000').replace(/\/+$/, '');

// API request timeout in milliseconds
const API_TIMEOUT_MS = 10000;

// =============================================================================
// Gemini LLM Setup
// =============================================================================

const ai = new GoogleGenerativeAI(GEMINI_API_KEY);
const model = ai.getGenerativeModel({ model: 'gemini-2.5-flash' });

// =============================================================================
// Discord Client Setup
// =============================================================================

const client = new Client({
    intents: [
        GatewayIntentBits.Guilds,
        GatewayIntentBits.GuildMessages,
        GatewayIntentBits.MessageContent
    ]
});

// =============================================================================
// Room Name Aliases
// Maps user-friendly shorthand names to the API-compatible slug format.
// The backend supports fuzzy matching, but we normalize common aliases here
// to ensure consistent results.
// =============================================================================

const ROOM_ALIASES = {
    'drawing':      'drawing_room',
    'drawingroom':  'drawing_room',
    'drawing_room': 'drawing_room',
    'draw':         'drawing_room',
    'work1':        'work_room_1',
    'workroom1':    'work_room_1',
    'work_room_1':  'work_room_1',
    'wr1':          'work_room_1',
    'work2':        'work_room_2',
    'workroom2':    'work_room_2',
    'work_room_2':  'work_room_2',
    'wr2':          'work_room_2',
};

// =============================================================================
// Backend API Client
// All functions use native fetch (Node 18+) with AbortController for timeout.
// =============================================================================

/**
 * Internal helper — performs a GET request to the backend with timeout handling.
 * @param {string} path - The API path (e.g. '/api/status')
 * @returns {Promise<object>} Parsed JSON response
 * @throws {Error} On network errors, timeouts, or non-OK HTTP responses
 */
async function apiGet(path) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), API_TIMEOUT_MS);

    try {
        const res = await fetch(`${BACKEND_URL}${path}`, {
            signal: controller.signal,
            headers: { 'Accept': 'application/json' }
        });

        if (!res.ok) {
            throw new Error(`Backend returned HTTP ${res.status}: ${res.statusText}`);
        }

        return await res.json();
    } catch (err) {
        if (err.name === 'AbortError') {
            throw new Error('Backend request timed out');
        }
        throw err;
    } finally {
        clearTimeout(timeout);
    }
}

/** Fetch status of all devices grouped by room. */
async function fetchStatus() {
    return apiGet('/api/status');
}

/** Fetch status of a specific room. Normalizes the room name via aliases first. */
async function fetchRoomStatus(room) {
    const normalized = normalizeRoomName(room);
    return apiGet(`/api/status/${encodeURIComponent(normalized)}`);
}

/** Fetch power usage, billing, and per-room breakdown. */
async function fetchUsage() {
    return apiGet('/api/usage');
}

/** Fetch active and recent alerts. */
async function fetchAlerts() {
    return apiGet('/api/alerts');
}

/**
 * Normalize a user-provided room name to a backend-compatible slug.
 * Strips spaces, lowercases, and checks the alias map.
 * Falls through to the raw input if no alias matches (the backend does fuzzy matching too).
 */
function normalizeRoomName(input) {
    const key = input.toLowerCase().replace(/[\s-]+/g, '');
    return ROOM_ALIASES[key] || input;
}

// =============================================================================
// Template Fallback Formatter
// Produces clean, emoji-decorated strings from raw API data when the LLM is
// unavailable or errors out. This is the reliable baseline.
// =============================================================================

/**
 * Build a deterministic, formatted response string from API data.
 * @param {'status'|'room'|'usage'} command - Which command was invoked
 * @param {object} data - The raw API response data
 * @returns {string} A human-readable message
 */
function formatTemplate(command, data) {
    switch (command) {

        case 'status': {
            // data is { "Drawing Room": [devices], "Work Room 1": [devices], ... }
            const roomSummaries = Object.entries(data).map(([roomName, devices]) => {
                const fansOn  = devices.filter(d => d.type === 'fan'   && d.status === 'on').length;
                const lightsOn = devices.filter(d => d.type === 'light' && d.status === 'on').length;

                if (fansOn === 0 && lightsOn === 0) {
                    return `${roomName}: all off`;
                }

                const parts = [];
                if (fansOn > 0)   parts.push(`${fansOn} fan${fansOn > 1 ? 's' : ''} ON`);
                if (lightsOn > 0) parts.push(`${lightsOn} light${lightsOn > 1 ? 's' : ''} ON`);
                return `${roomName}: ${parts.join(', ')}`;
            });

            return `📊 ${roomSummaries.join(' | ')}`;
        }

        case 'room': {
            // data is an array of device objects for a single room
            if (!Array.isArray(data) || data.length === 0) {
                return '🏠 No devices found for that room.';
            }

            const roomName = data[0].room;
            const totalWatts = data
                .filter(d => d.status === 'on')
                .reduce((sum, d) => sum + (d.power_watts || 0), 0);

            const deviceLines = data.map(d => {
                const statusLabel = d.status === 'on' ? `ON (${d.power_watts}W)` : 'OFF';
                return `${d.name} ${statusLabel}`;
            });

            return `🏠 ${roomName}: ${deviceLines.join(', ')} — Total: ${totalWatts}W`;
        }

        case 'usage': {
            // data is { total_watts, today_kwh, estimated_bill, rate_per_kwh, rooms: {...} }
            const watts = data.total_watts ?? 0;
            const kwh   = data.today_kwh ?? 0;
            const bill  = data.estimated_bill ?? 0;
            return `⚡ Current power: ${watts}W | Today's usage: ${kwh} kWh | Estimated bill: ৳${bill.toFixed(2)}`;
        }

        default:
            return '❓ Unknown command. Try `!status`, `!room <name>`, or `!usage`.';
    }
}

// =============================================================================
// LLM-Humanized Response Formatter
// Tries Gemini first for a natural, conversational response.
// Falls back to the template formatter on any failure.
// =============================================================================

/**
 * Generate a friendly, conversational response using Gemini LLM.
 * Degrades gracefully to the template formatter on any error.
 *
 * @param {'status'|'room'|'usage'} command - The command type
 * @param {object} data - Raw API response data
 * @returns {Promise<string>} The formatted message
 */
async function formatResponse(command, data) {
    try {
        const promptMap = {
            status: `You are a friendly office assistant bot monitoring a smart office system. Here is the current device status for all rooms:\n${JSON.stringify(data, null, 2)}\n\nInstructions:\n1. Summarize which fans and lights are ON in each room naturally.\n2. If the user asks anything outside the project context, acknowledge it's not part of the system and refuse to answer.\n3. Do NOT hardcode any data; only use numbers fetched from the backend data provided.\n4. If numbers need to be derived, do the calculation.\n5. Keep response under 50 tokens and don't use markdown.`,

            room: `You are a friendly office assistant bot monitoring a smart office system. Here is the device status for a room:\n${JSON.stringify(data, null, 2)}\n\nInstructions:\n1. Describe each device's status, wattage, and total power draw naturally.\n2. If the user asks anything outside the project context, acknowledge it's not part of the system and refuse to answer.\n3. Do NOT hardcode any data; only use numbers fetched from the backend data provided.\n4. If numbers need to be derived, do the calculation.\n5. Keep response under 50 tokens and don't use markdown.`,

            usage: `You are a friendly office assistant bot monitoring a smart office system. Here is the current power usage data:\n${JSON.stringify(data, null, 2)}\n\nInstructions:\n1. Summarize the current power consumption, today's usage in kWh, and estimated bill naturally.\n2. If the user asks anything outside the project context, acknowledge it's not part of the system and refuse to answer.\n3. Do NOT hardcode any data; only use numbers fetched from the backend data provided.\n4. If numbers need to be derived, do the calculation.\n5. Keep response under 50 tokens and don't use markdown.`,
        };

        const prompt = promptMap[command];
        if (!prompt) {
            return formatTemplate(command, data);
        }

        const result = await model.generateContent(prompt);
        const text = result.response.text();

        // Sanity check — if Gemini returns nothing useful, fall back
        if (!text || text.trim().length < 5) {
            console.warn('[Gemini] Empty or too-short response, using template fallback.');
            return formatTemplate(command, data);
        }

        return text.trim();

    } catch (err) {
        console.error('[Gemini] LLM call failed, using template fallback:', err.message);
        return formatTemplate(command, data);
    }
}

// =============================================================================
// Command Router
// Parses user input and dispatches to the appropriate handler.
// =============================================================================

/**
 * Parse and execute a command string.
 * @param {string} input - The raw user input (after stripping mention, if any)
 * @returns {Promise<string>} The response message to send back
 */
async function handleCommand(input) {
    const trimmed = input.trim();

    // --- !status ---
    if (trimmed === '!status' || trimmed === 'status') {
        const data = await fetchStatus();
        return formatResponse('status', data);
    }

    // --- !room <name> ---
    const roomMatch = trimmed.match(/^!?room\s+(.+)$/i);
    if (roomMatch) {
        const roomName = roomMatch[1].trim();
        const data = await fetchRoomStatus(roomName);
        return formatResponse('room', data);
    }

    // --- !usage ---
    if (trimmed === '!usage' || trimmed === 'usage') {
        const data = await fetchUsage();
        return formatResponse('usage', data);
    }

    // --- !alerts ---
    if (trimmed === '!alerts' || trimmed === 'alerts') {
        const data = await fetchAlerts();
        const activeCount = data.active?.length ?? 0;
        if (activeCount === 0) {
            return '✅ No active alerts right now. Everything looks good!';
        }
        const summaries = data.active.map(a => `⚠️ ${a.message || a.type || 'Alert'}`);
        return `🚨 ${activeCount} active alert${activeCount > 1 ? 's' : ''}:\n${summaries.join('\n')}`;
    }

    // --- Natural Query / Unrecognized ---
    try {
        const [statusData, usageData, alertsData] = await Promise.all([
            fetchStatus().catch(() => null),
            fetchUsage().catch(() => null),
            fetchAlerts().catch(() => null)
        ]);

        const contextData = { status: statusData, usage: usageData, alerts: alertsData };

        const prompt = `You are a friendly office assistant bot monitoring a smart office system.
Here is the current live data from the backend:
${JSON.stringify(contextData, null, 2)}

User query: "${trimmed}"

Instructions:
1. Answer the user's query naturally based ONLY on the provided live data.
2. If the user asks anything outside the context of this project, you must acknowledge that it is not part of the system and you cannot answer it.
3. Do NOT hardcode any data in the output. Only show the numbers fetched from the backend data above.
4. If some numbers need to be derived, perform the calculation.
5. Keep your response under 100 words and do not use markdown formatting.`;

        const result = await model.generateContent(prompt);
        const text = result.response.text();

        if (text && text.trim().length >= 5) {
            return text.trim();
        }
    } catch (err) {
        console.error('[Gemini] Natural query fallback failed:', err.message);
    }

    return "👋 Hey! Here are my available commands:\n• `!status` — Overview of all rooms\n• `!room <name>` — Details for a specific room\n• `!usage` — Power consumption & billing\n• `!alerts` — Active alerts";
}

// =============================================================================
// Discord Event Handlers
// =============================================================================

client.once('ready', () => {
    console.log(`✅ Bot online — logged in as ${client.user.tag}`);
    console.log(`📡 Backend URL: ${BACKEND_URL}`);
});

client.on('messageCreate', async (msg) => {
    // Ignore messages from bots (including ourselves)
    if (msg.author.bot) return;

    const isCommand  = msg.content.startsWith('!');
    const isMentioned = msg.mentions.has(client.user);

    // Only respond to ! commands or @mentions
    if (!isCommand && !isMentioned) return;

    let placeholder;

    try {
        // Show a "thinking" indicator while we fetch data
        placeholder = await msg.reply('`Analyzing...`');

        let userInput = msg.content.trim();

        // Strip the @mention from the message to extract the actual command
        if (isMentioned) {
            const mentionRegex = new RegExp(`<@!?${client.user.id}>`, 'g');
            userInput = userInput.replace(mentionRegex, '').trim();

            // If the user just @mentioned the bot with no command, show help
            if (!userInput) {
                await placeholder.edit(
                    "👋 Hey! Here are my available commands:\n" +
                    "• `!status` — Overview of all rooms\n" +
                    "• `!room <name>` — Details for a specific room\n" +
                    "• `!usage` — Power consumption & billing\n" +
                    "• `!alerts` — Active alerts"
                );
                return;
            }
        }

        // Route the command and get the response
        const response = await handleCommand(userInput);
        await placeholder.edit(response);

    } catch (err) {
        console.error('[Bot] Error handling message:', err);

        const userMessage = isBackendError(err)
            ? '🔌 Backend is offline, please try again later.'
            : `❌ Something went wrong: ${err.message || err}`;

        if (placeholder) {
            await placeholder.edit(userMessage);
        }
    }
});

/**
 * Check if an error is likely a backend connectivity issue.
 */
function isBackendError(err) {
    const msg = (err.message || '').toLowerCase();
    return (
        msg.includes('econnrefused') ||
        msg.includes('enotfound') ||
        msg.includes('timed out') ||
        msg.includes('fetch failed') ||
        msg.includes('network')
    );
}

// =============================================================================
// Start the bot
// =============================================================================

client.login(DISCORD_TOKEN);
