import { useState, useEffect, useRef } from 'react'
import api from '../api/client'

const CHEST_TS_KEY = 'cloudrisk_chest_ts'
const COOLDOWN_MS = 6 * 60 * 60 * 1000

const REWARDS = [
  { icon: '⚔️', label: 'Tropas de refuerzo', steps: 800 },
  { icon: '🏃', label: 'Marcha de campaña', steps: 1200 },
  { icon: '💪', label: 'Batallón de élite', steps: 600 },
  { icon: '⭐', label: 'Gloria de batalla', steps: 1500 },
  { icon: '🎯', label: 'Patrulla de exploración', steps: 500 },
]

function getRemainingMs() {
  const ts = parseInt(localStorage.getItem(CHEST_TS_KEY) || '0', 10)
  return ts ? Math.max(0, COOLDOWN_MS - (Date.now() - ts)) : 0
}

function formatCountdown(ms) {
  return `${Math.floor(ms / 3600000)}h ${Math.floor((ms % 3600000) / 60000)}m`
}

export default function RewardChest({ onRewardClaimed }) {
  const [remainingMs, setRemainingMs] = useState(getRemainingMs)
  const [claiming, setClaiming] = useState(false)
  const [claimed, setClaimed] = useState(null)
  const dismissRef = useRef(null)

  const isAvailable = remainingMs <= 0

  // Run interval only while on cooldown; restart only when availability flips
  useEffect(() => {
    if (isAvailable) return
    const interval = setInterval(() => setRemainingMs(getRemainingMs()), 1000)
    return () => clearInterval(interval)
  }, [isAvailable])

  // Cleanup dismiss timeout on unmount
  useEffect(() => () => clearTimeout(dismissRef.current), [])

  const handleClaim = async () => {
    if (!isAvailable || claiming) return
    const reward = REWARDS[Math.floor(Math.random() * REWARDS.length)]
    setClaiming(true)
    try {
      await api.post('/api/v1/steps/sync', { steps: reward.steps })
      localStorage.setItem(CHEST_TS_KEY, String(Date.now()))
      setClaimed(reward)
      setRemainingMs(COOLDOWN_MS)
      onRewardClaimed?.()
      dismissRef.current = setTimeout(() => setClaimed(null), 3000)
    } catch {
      // network errors are non-critical
    } finally {
      setClaiming(false)
    }
  }

  const glowStyle = isAvailable && !claimed
    ? { animation: 'chest-pulse 1.4s ease-in-out infinite' }
    : {}

  return (
    <button
      className="action-btn action-btn-orange"
      onClick={handleClaim}
      disabled={!isAvailable || claiming}
      style={{ cursor: isAvailable ? 'pointer' : 'default', ...glowStyle }}
      title="Premio del cofre"
    >
      {claimed ? (
        <><span className="action-btn-icon">{claimed.icon}</span>{claimed.label}</>
      ) : (
        <><span className="action-btn-icon">📦</span>{isAvailable ? '¡Abrir!' : formatCountdown(remainingMs)}</>
      )}
    </button>
  )
}
