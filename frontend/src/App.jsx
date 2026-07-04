import { useState, useEffect, useCallback, useRef } from 'react'
import { useSocket } from './hooks/useSocket'
import { fetchStatus, fetchPower, fetchUsage, fetchAlerts, fetchMode } from './api'
import Header from './components/Header'
import DevicePanel from './components/DevicePanel'
import PowerPanel from './components/PowerPanel'
import AlertsPanel from './components/AlertsPanel'
import SettingsPanel from './components/SettingsPanel'
import Toast from './components/Toast'

export default function App() {
  const [devices, setDevices] = useState(null)
  const [power, setPower] = useState(null)
  const [usage, setUsage] = useState(null)
  const [alerts, setAlerts] = useState(null)
  const [mode, setMode] = useState('automatic')
  const [isAfterHours, setIsAfterHours] = useState(false)
  const [initialLoaded, setInitialLoaded] = useState(false)
  const [toastMessage, setToastMessage] = useState('')
  const seenAlerts = useRef(new Set())

  const { connected, on } = useSocket()

  // Initial data load via REST
  const loadInitialData = useCallback(async () => {
    try {
      const [statusData, powerData, usageData, alertsData, modeData] = await Promise.allSettled([
        fetchStatus(),
        fetchPower(),
        fetchUsage(),
        fetchAlerts(),
        fetchMode()
      ])

      if (statusData.status === 'fulfilled') setDevices(statusData.value)
      if (powerData.status === 'fulfilled') setPower(powerData.value)
      if (usageData.status === 'fulfilled') setUsage(usageData.value)
      if (alertsData.status === 'fulfilled') setAlerts(alertsData.value)
      if (modeData.status === 'fulfilled') {
        const m = modeData.value?.mode ?? modeData.value
        if (typeof m === 'string') setMode(m)
        if (modeData.value?.is_after_hours !== undefined) setIsAfterHours(modeData.value.is_after_hours)
      }

      setInitialLoaded(true)
    } catch (err) {
      console.error('Failed to load initial data:', err)
    }
  }, [])

  useEffect(() => {
    loadInitialData()
  }, [loadInitialData])

  // Re-fetch when reconnecting
  useEffect(() => {
    if (connected && initialLoaded) {
      loadInitialData()
    }
  }, [connected, initialLoaded, loadInitialData])

  // Socket.IO real-time listeners
  useEffect(() => {
    const unsubs = [
      on('state_update', (data) => {
        if (data.devices) setDevices(data.devices)
        if (data.mode) setMode(data.mode)
        if (data.is_after_hours !== undefined) setIsAfterHours(data.is_after_hours)
      }),
      on('power_update', (data) => {
        setPower(data)
        // Also update usage-related fields if present
        if (data.today_kwh != null) {
          setUsage((prev) => ({
            ...prev,
            today_kwh: data.today_kwh,
            estimated_bill: data.estimated_bill,
            rate_per_kwh: data.rate_per_kwh
          }))
        }
      }),
      on('alerts_update', (data) => {
        setAlerts(data)
        
        // Check for new red alerts (room_idle) to show toast
        if (data.active) {
          const currentActiveIds = new Set(data.active.map(a => a.id))
          
          // Remove resolved alerts from seen so they can fire again later
          for (const id of seenAlerts.current) {
            if (!currentActiveIds.has(id)) {
              seenAlerts.current.delete(id)
            }
          }

          for (const alert of data.active) {
            if (alert.type === 'room_idle' && !seenAlerts.current.has(alert.id)) {
              setToastMessage(alert.message)
              seenAlerts.current.add(alert.id)
            }
          }
        }
      })
    ]

    return () => unsubs.forEach((unsub) => unsub())
  }, [on])

  function handleModeChange(newMode) {
    setMode(newMode)
  }

  // Extract room power from power data
  const roomPower = power?.rooms ?? null

  return (
    <div className="app-container">
      <Toast message={toastMessage} onClose={() => setToastMessage('')} />
      <Header mode={mode} connected={connected} onModeChange={handleModeChange} isAfterHours={isAfterHours} />

      <div className="dashboard-grid">
        {/* Left Column: Devices and Settings */}
        <div className="left-column">
          <DevicePanel devices={devices} mode={mode} roomPower={roomPower} />
          <SettingsPanel />
        </div>

        {/* Right Column: Power + Alerts */}
        <div className="right-column">
          <PowerPanel power={power} usage={usage} />
          <AlertsPanel alerts={alerts} />
        </div>
      </div>

      {/* Reconnecting overlay */}
      {!connected && initialLoaded && (
        <div className="reconnecting-overlay">
          <div className="reconnecting-spinner" />
          <span className="reconnecting-text">Reconnecting…</span>
          <span className="reconnecting-sub">Attempting to re-establish connection</span>
        </div>
      )}
    </div>
  )
}
