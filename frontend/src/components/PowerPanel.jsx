export default function PowerPanel({ power, usage }) {
  const totalWatts = power?.total_watts ?? 0
  const rooms = power?.rooms ?? {}
  const todayKwh = usage?.today_kwh ?? power?.today_kwh ?? 0
  const estimatedBill = usage?.estimated_bill ?? power?.estimated_bill ?? 0
  const ratePerKwh = usage?.rate_per_kwh ?? power?.rate_per_kwh ?? 0

  const maxRoomWatts = Math.max(1, ...Object.values(rooms))

  const hasData = power != null

  if (!hasData) {
    return (
      <div className="glass-card power-panel">
        <div className="power-panel-title">
          <span className="section-icon">⚡</span>
          <h2>Power &amp; Billing</h2>
        </div>
        <div className="loading-state">
          <div className="loading-spinner" />
          <span className="loading-text">Waiting for power data…</span>
        </div>
      </div>
    )
  }

  return (
    <div className="glass-card power-panel">
      <div className="power-panel-title">
        <span className="section-icon">⚡</span>
        <h2>Power &amp; Billing</h2>
      </div>

      {/* Total Watts */}
      <div className="power-total">
        <span className="power-total-icon">🔌</span>
        <span className="power-total-value">{totalWatts}</span>
        <span className="power-total-unit">W</span>
      </div>

      {/* Per-room breakdown */}
      <div className="power-rooms">
        {Object.entries(rooms).map(([room, watts]) => (
          <div className="power-room-row" key={room}>
            <span className="power-room-name">{room}</span>
            <div className="power-room-bar-bg">
              <div
                className="power-room-bar-fill"
                style={{ width: `${(watts / maxRoomWatts) * 100}%` }}
              />
            </div>
            <span className="power-room-watts">{watts}W</span>
          </div>
        ))}
      </div>

      {/* Stats */}
      <div className="power-stats">
        <div className="power-stat-card">
          <div className="power-stat-icon">📊</div>
          <div className="power-stat-value">{Number(todayKwh).toFixed(3)}</div>
          <div className="power-stat-label">kWh Today</div>
        </div>
        <div className="power-stat-card">
          <div className="power-stat-icon">💰</div>
          <div className="power-stat-value">৳{Number(estimatedBill).toFixed(2)}</div>
          <div className="power-stat-label">Est. Bill</div>
        </div>
      </div>

      {ratePerKwh > 0 && (
        <div className="power-rate-note">
          Rate: ৳{ratePerKwh}/kWh
        </div>
      )}
    </div>
  )
}
