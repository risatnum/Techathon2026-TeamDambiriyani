import { useEffect } from 'react'

export default function Toast({ message, onClose }) {
  useEffect(() => {
    if (message) {
      const timer = setTimeout(() => {
        onClose()
      }, 5000)
      return () => clearTimeout(timer)
    }
  }, [message, onClose])

  if (!message) return null

  return (
    <div className="toast-container">
      <div className="toast red-alert">
        <div className="toast-icon">🚨</div>
        <div className="toast-content">
          <div className="toast-title">Red Alert</div>
          <div className="toast-message">{message}</div>
        </div>
        <button className="toast-close" onClick={onClose}>×</button>
      </div>
    </div>
  )
}
