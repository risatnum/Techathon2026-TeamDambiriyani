function formatTimestamp(isoString) {
  if (!isoString) return ''
  try {
    const date = new Date(isoString)
    return date.toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true
    }) + ', ' + date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric'
    })
  } catch {
    return isoString
  }
}

function AlertCard({ alert }) {
  const isAfterHours = alert.type === 'after_hours'
  const icon = isAfterHours ? '⚠️' : '🔴'
  const typeLabel = isAfterHours ? 'After Hours' : 'Room Idle'

  return (
    <div className={`alert-card ${alert.type}`}>
      <span className="alert-icon">{icon}</span>
      <div className="alert-content">
        <div className="alert-message">{alert.message}</div>
        <div className="alert-meta">
          <span className={`alert-type-badge ${alert.type}`}>{typeLabel}</span>
          <span className="alert-timestamp">{formatTimestamp(alert.timestamp)}</span>
        </div>
      </div>
    </div>
  )
}

export default function AlertsPanel({ alerts }) {
  const activeAlerts = alerts?.active ?? []

  return (
    <div className="glass-card alerts-panel">
      <div className="alerts-panel-title">
        <span className="section-icon">🔔</span>
        <h2>Active Alerts</h2>
        {activeAlerts.length > 0 && (
          <span className="alert-count-badge">{activeAlerts.length}</span>
        )}
      </div>

      {activeAlerts.length === 0 ? (
        <div className="alerts-clear">
          <span className="alerts-clear-icon">✅</span>
          <span className="alerts-clear-text">All Clear</span>
          <span className="alerts-clear-sub">No active alerts right now</span>
        </div>
      ) : (
        <div className="alerts-scroll">
          {activeAlerts.map((alert) => (
            <AlertCard key={alert.id} alert={alert} />
          ))}
        </div>
      )}
    </div>
  )
}
