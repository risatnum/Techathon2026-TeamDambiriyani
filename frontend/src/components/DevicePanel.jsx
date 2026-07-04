import { useState } from 'react'
import { toggleDevice } from '../api'

function DeviceNode({ device, isManual }) {
  const [toggling, setToggling] = useState(false)
  const isOn = device.status === 'on'
  const isFan = device.type === 'fan'

  async function handleToggle(e) {
    e.stopPropagation()
    if (!isManual || toggling) return
    setToggling(true)
    try {
      await toggleDevice(device.id, isOn ? 'off' : 'on')
    } catch (err) {
      console.error('Failed to toggle device:', err)
    } finally {
      setToggling(false)
    }
  }

  // Derive a simple label like "F 1" or "L 2"
  const label = `${device.type === 'fan' ? 'FAN' : 'LIGHT'} ${device.name.split(' ')[1]}`

  return (
    <div 
      className={`device-node ${device.type} ${isOn ? 'on' : 'off'} ${isManual ? 'interactive' : ''}`}
      onClick={isManual ? handleToggle : undefined}
      title={`${device.name} - ${isOn ? 'ON' : 'OFF'} (${device.power_watts}W)`}
    >
      <div className="device-node-icon">
        {isFan ? (
          <svg viewBox="0 0 100 100" className={`fan-svg ${isOn ? 'spinning' : ''}`}>
            <circle cx="50" cy="50" r="45" fill="none" stroke="currentColor" strokeWidth="2" opacity="0.3"/>
            <circle cx="50" cy="50" r="10" fill="currentColor" />
            <g className="spinning-group">
              <path d="M50 45 Q 60 20 50 5 Q 40 20 50 45" fill="currentColor" transform="rotate(0, 50, 50)" />
              <path d="M50 45 Q 60 20 50 5 Q 40 20 50 45" fill="currentColor" transform="rotate(120, 50, 50)" />
              <path d="M50 45 Q 60 20 50 5 Q 40 20 50 45" fill="currentColor" transform="rotate(240, 50, 50)" />
            </g>
          </svg>
        ) : (
          <div className={`light-bulb ${isOn ? 'glowing' : ''}`}></div>
        )}
      </div>
      <div className="device-node-label">{label}</div>
    </div>
  )
}

export default function DevicePanel({ devices, mode, roomPower }) {
  const isManual = mode === 'manual'
  
  if (!devices) {
    return (
      <div className="glass-card">
        <div className="loading-state">
          <div className="loading-spinner" />
          <span className="loading-text">Waiting for device data…</span>
        </div>
      </div>
    )
  }

  // Helper to extract devices for a room
  const getDevices = (roomName) => devices[roomName] || []
  
  return (
    <div className="floor-plan-container">
      <div className="device-panel-title" style={{ padding: '0 20px', marginBottom: '10px' }}>
        <span className="section-icon">🗺️</span>
        <h2>Office Floor Plan</h2>
        {isManual && <span className="manual-badge">Manual Mode Active</span>}
      </div>

      <div className="floor-plan blueprint-style">
        {['Drawing Room', 'Work Room 1', 'Work Room 2'].map(roomName => {
          const roomDevices = getDevices(roomName)
          const watts = roomPower && roomPower[roomName] != null ? roomPower[roomName] : 0
          
          return (
            <div className="blueprint-room" key={roomName}>
              <div className="room-label">
                {roomName.toUpperCase()}
                <span className="room-power-label">{watts}W</span>
              </div>
              
              <div className="room-devices-area">
                {roomDevices.map((device, i) => (
                  <DeviceNode key={device.id} device={device} isManual={isManual} />
                ))}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
