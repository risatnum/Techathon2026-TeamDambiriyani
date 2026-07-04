import { useState } from 'react'
import { setMode as apiSetMode } from '../api'

export default function Header({ mode, connected, onModeChange, isAfterHours }) {
  const [switching, setSwitching] = useState(false)

  async function handleModeChange(newMode) {
    if (newMode === mode || switching) return
    setSwitching(true)
    try {
      await apiSetMode(newMode)
      onModeChange(newMode)
    } catch (err) {
      console.error('Failed to switch mode:', err)
    } finally {
      setSwitching(false)
    }
  }

  return (
    <header className="header">
      <div className="header-left">
        <div className="header-logo">🏢</div>
        <h1 className="header-title">Office Monitor</h1>
      </div>

      <div className="header-right">
        <div className="connection-status">
          <span className={`connection-dot ${connected ? 'connected' : 'disconnected'}`} />
          <span>{connected ? 'Live' : 'Disconnected'}</span>
        </div>

        <div className="mode-toggle">
          <input
            type="radio"
            name="mode"
            id="mode-auto"
            value="automatic"
            checked={mode === 'automatic'}
            onChange={() => handleModeChange('automatic')}
            disabled={switching}
          />
          <label htmlFor="mode-auto">Automatic</label>

          <input
            type="radio"
            name="mode"
            id="mode-manual"
            value="manual"
            checked={mode === 'manual'}
            onChange={() => handleModeChange('manual')}
            disabled={switching}
          />
          <label htmlFor="mode-manual">Manual</label>
        </div>
      </div>
    </header>
  )
}
