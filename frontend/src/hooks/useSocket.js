import { useEffect, useRef, useState, useCallback } from 'react'
import { io } from 'socket.io-client'

const BACKEND_URL = 'http://localhost:8000'

export function useSocket() {
  const socketRef = useRef(null)
  const [connected, setConnected] = useState(false)

  useEffect(() => {
    const socket = io(BACKEND_URL, {
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionAttempts: Infinity,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 10000,
      randomizationFactor: 0.5
    })

    socketRef.current = socket

    socket.on('connect', () => {
      console.log('[Socket] Connected:', socket.id)
      setConnected(true)
    })

    socket.on('disconnect', (reason) => {
      console.log('[Socket] Disconnected:', reason)
      setConnected(false)
    })

    socket.on('connect_error', (err) => {
      console.warn('[Socket] Connection error:', err.message)
      setConnected(false)
    })

    return () => {
      socket.disconnect()
      socketRef.current = null
    }
  }, [])

  const on = useCallback((event, handler) => {
    const socket = socketRef.current
    if (!socket) return () => {}
    socket.on(event, handler)
    return () => socket.off(event, handler)
  }, [])

  return { connected, socket: socketRef.current, on }
}
