import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * useWebSocket — resilient WS client for CloudRISK.
 *
 * Features:
 *  - Exponential backoff reconnect (1s → 30s, cap), max 10 attempts
 *  - Heartbeat ping every 25s to keep Cloud Run from killing idle sockets
 *  - Status tri-state: 'connecting' | 'open' | 'closed' | 'failed'
 *  - Safe against stale closures: onMessage kept in ref
 *  - Clean teardown on userId change or unmount
 */
export default function useWebSocket(userId, onMessage) {
  const ws = useRef(null)
  const reconnectTimer = useRef(null)
  const heartbeatTimer = useRef(null)
  const retryCount = useRef(0)
  const manuallyClosed = useRef(false)
  const onMessageRef = useRef(onMessage)
  const [status, setStatus] = useState('idle')

  useEffect(() => { onMessageRef.current = onMessage }, [onMessage])

  const clearTimers = useCallback(() => {
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current)
      reconnectTimer.current = null
    }
    if (heartbeatTimer.current) {
      clearInterval(heartbeatTimer.current)
      heartbeatTimer.current = null
    }
  }, [])

  const connect = useCallback(() => {
    if (!userId) return
    if (manuallyClosed.current) return
    // WS URL resolution (prod no recibe VITE_WS_URL como build-arg, así que
    // derivamos de VITE_API_URL cambiando el esquema: https→wss, http→ws).
    // Fallback final: ws://localhost:8080 para dev sin env vars.
    const explicitWs = import.meta.env.VITE_WS_URL
    const apiUrl = import.meta.env.VITE_API_URL
    const derivedWs = apiUrl
      ? apiUrl.replace(/^https:\/\//i, 'wss://').replace(/^http:\/\//i, 'ws://')
      : null
    const wsUrl = explicitWs || derivedWs || 'ws://localhost:8080'
    setStatus('connecting')

    let socket
    try {
      socket = new WebSocket(`${wsUrl}/ws/${userId}`)
    } catch (e) {
      setStatus('failed')
      return
    }
    ws.current = socket

    socket.onopen = () => {
      retryCount.current = 0
      setStatus('open')
      // Heartbeat every 25s — under Cloud Run's idle timeout
      heartbeatTimer.current = setInterval(() => {
        if (socket.readyState === WebSocket.OPEN) {
          try { socket.send(JSON.stringify({ event: 'ping' })) } catch {}
        }
      }, 25000)
    }

    socket.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        // Swallow server-side pong responses silently
        if (data?.event === 'pong') return
        onMessageRef.current?.(data)
      } catch (err) {
        // Ignore malformed payloads — don't crash the whole app
        console.debug('[WS] bad payload', err)
      }
    }

    socket.onerror = () => {
      // Let onclose drive the reconnect logic
      try { socket.close() } catch {}
    }

    socket.onclose = () => {
      clearTimers()
      if (manuallyClosed.current) {
        setStatus('closed')
        return
      }
      if (retryCount.current >= 10) {
        setStatus('failed')
        return
      }
      setStatus('closed')
      const delay = Math.min(1000 * (2 ** retryCount.current), 30000)
      retryCount.current += 1
      reconnectTimer.current = setTimeout(connect, delay)
    }
  }, [userId, clearTimers])

  useEffect(() => {
    manuallyClosed.current = false
    retryCount.current = 0
    connect()

    // M-6: reaccionar a eventos online/offline del navegador
    // — offline: cancelar timers y cerrar el socket (evita acumular retries inútiles)
    // — online:  resetear el contador y reconectar inmediatamente
    const handleOffline = () => {
      clearTimers()
      if (ws.current) {
        try { ws.current.close() } catch {}
        ws.current = null
      }
      setStatus('closed')
    }
    const handleOnline = () => {
      if (manuallyClosed.current) return
      retryCount.current = 0   // reset para no quedar atascado en 'failed'
      connect()
    }
    window.addEventListener('offline', handleOffline)
    window.addEventListener('online', handleOnline)

    return () => {
      manuallyClosed.current = true
      clearTimers()
      if (ws.current) {
        try { ws.current.close() } catch {}
        ws.current = null
      }
      window.removeEventListener('offline', handleOffline)
      window.removeEventListener('online', handleOnline)
    }
  }, [connect, clearTimers])

  const sendMessage = useCallback((data) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      try { ws.current.send(JSON.stringify(data)) } catch {}
    }
  }, [])

  return { sendMessage, status }
}
