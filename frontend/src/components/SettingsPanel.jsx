import { useState, useEffect } from 'react'
import { fetchSettings, updateSettings } from '../api'

export default function SettingsPanel() {
  const [settings, setSettings] = useState({
    office_open_time: '09:00',
    office_close_time: '17:00',
    room_idle_threshold_hours: 2.0
  })
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')

  useEffect(() => {
    fetchSettings().then(setSettings).catch(console.error)
  }, [])

  const handleChange = (e) => {
    const { name, value } = e.target
    setSettings(prev => ({
      ...prev,
      [name]: name === 'room_idle_threshold_hours' ? parseFloat(value) || 0 : value
    }))
  }

  const handleSave = async () => {
    setSaving(true)
    setMessage('')
    try {
      const res = await updateSettings(settings)
      setSettings(res.settings)
      setMessage('Settings saved successfully!')
      setTimeout(() => setMessage(''), 3000)
    } catch (err) {
      console.error(err)
      setMessage('Error saving settings.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="glass-card settings-panel">
      <div className="device-panel-title">
        <span className="section-icon">⚙️</span>
        <h2>System Settings</h2>
      </div>
      
      <div className="settings-grid">
        <div className="setting-item">
          <label htmlFor="office_open_time">Office Start Time</label>
          <input
            type="time"
            id="office_open_time"
            name="office_open_time"
            value={settings.office_open_time}
            onChange={handleChange}
          />
        </div>
        
        <div className="setting-item">
          <label htmlFor="office_close_time">Office End Time</label>
          <input
            type="time"
            id="office_close_time"
            name="office_close_time"
            value={settings.office_close_time}
            onChange={handleChange}
          />
        </div>
        
        <div className="setting-item">
          <label htmlFor="room_idle_threshold_hours">Red Alert Duration (hours)</label>
          <input
            type="number"
            id="room_idle_threshold_hours"
            name="room_idle_threshold_hours"
            step="0.1"
            min="0"
            value={settings.room_idle_threshold_hours}
            onChange={handleChange}
          />
        </div>
      </div>
      
      <div className="settings-actions">
        <button className="mode-btn manual" onClick={handleSave} disabled={saving}>
          {saving ? 'Saving...' : 'Save Settings'}
        </button>
        {message && <span className="settings-message">{message}</span>}
      </div>
    </div>
  )
}
