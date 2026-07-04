const BASE_URL = 'http://localhost:8000'

async function request(path, options = {}) {
  try {
    const res = await fetch(`${BASE_URL}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options
    })
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${res.statusText}`)
    }
    return await res.json()
  } catch (err) {
    console.error(`API Error [${path}]:`, err)
    throw err
  }
}

export function fetchStatus() {
  return request('/api/status')
}

export function fetchPower() {
  return request('/api/power')
}

export function fetchUsage() {
  return request('/api/usage')
}

export function fetchAlerts() {
  return request('/api/alerts')
}

export function fetchMode() {
  return request('/api/mode')
}

export function setMode(mode) {
  return request('/api/mode', {
    method: 'POST',
    body: JSON.stringify({ mode })
  })
}

export function toggleDevice(deviceId, status) {
  return request(`/api/devices/${deviceId}`, {
    method: 'POST',
    body: JSON.stringify({ status })
  })
}

export function fetchSettings() {
  return request('/api/settings')
}

export function updateSettings(settings) {
  return request('/api/settings', {
    method: 'POST',
    body: JSON.stringify(settings)
  })
}
