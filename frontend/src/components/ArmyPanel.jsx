import { useEffect, useMemo, useState } from 'react'
import api from '../api/client'

export default function ArmyPanel({ onClose, selectedZone, onDeployed }) {
  const [balance, setBalance] = useState(null)
  const [amount, setAmount] = useState(1)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const refreshBalance = async () => {
    try {
      const response = await api.get('/api/v1/armies/balance')
      setBalance(response.data)
    } catch {
      setBalance(null)
    }
  }

  useEffect(() => { refreshBalance() }, [])

  useEffect(() => {
    setAmount(1)
    setError('')
    setSuccess('')
  }, [selectedZone?.id])

  const maxAvailable = Math.max(1, Number(balance?.armies_available || 1))
  const safeAmount = Math.max(1, Math.min(maxAvailable, Number(amount || 1)))
  const suggestedAmount = useMemo(() => {
    if (!selectedZone) return 1
    const current = Number(selectedZone.total_armies || 0)
    if (maxAvailable <= 3) return maxAvailable
    if (current < 10) return Math.min(maxAvailable, 6)
    if (current < 20) return Math.min(maxAvailable, 4)
    return Math.min(maxAvailable, 3)
  }, [maxAvailable, selectedZone])

  const applyAmount = (next) => {
    setAmount(Math.max(1, Math.min(maxAvailable, Number(next || 1))))
  }

  const deployArmies = async (event) => {
    event.preventDefault()
    if (!selectedZone) return
    setError('')
    setSuccess('')
    setLoading(true)
    try {
      // Contract endpoint: accepts both 'amount' (legacy) and 'armies' (contract).
      // player_id is inferred from JWT sub when not in body.
      const response = await api.post('/api/v1/actions/place', {
        location_id: selectedZone.id,
        armies: safeAmount,
      })
      setSuccess(response.data?.message || `${safeAmount} tropas desplegadas en ${selectedZone.name}.`)
      await refreshBalance()
      onDeployed?.({ zoneId: selectedZone.id, amount: safeAmount })
      setAmount(1)
    } catch (err) {
      setError(err.response?.data?.detail || 'No se han podido desplegar tropas.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="panel">
      <div className="panel-header">
        <h2>{'\uD83D\uDEA9'} Refuerzo T&aacute;ctico</h2>
        <button onClick={onClose}>{'\u2715'}</button>
      </div>
      <div className="panel-body">
        {/* Balance grid */}
        {balance && (
          <div className="deploy-balance">
            <div className="deploy-metric">
              <span className="deploy-metric-label">Disponibles</span>
              <strong className="deploy-metric-value">{Number(balance.armies_available || 0).toLocaleString()}</strong>
            </div>
            <div className="deploy-metric">
              <span className="deploy-metric-label">Hoy</span>
              <strong className="deploy-metric-value">{Number(balance.armies_earned_today || 0).toLocaleString()}</strong>
            </div>
            <div className="deploy-metric">
              <span className="deploy-metric-label">Total</span>
              <strong className="deploy-metric-value">{Number(balance.armies_total_earned || 0).toLocaleString()}</strong>
            </div>
          </div>
        )}

        <div className="ornament">{'\u2500\u2500\u2500 \u2726 \u2500\u2500\u2500'}</div>

        {!selectedZone ? (
          <p className="empty-msg">
            Selecciona una zona en el mapa para desplegar tropas.
          </p>
        ) : (
          <>
            {/* Target zone card */}
            <div className="deploy-target">
              <div className="deploy-target-header">
                <div>
                  <span className="deploy-target-eyebrow">Objetivo activo</span>
                  <span className="deploy-target-name">{selectedZone.name}</span>
                </div>
                <span className="deploy-target-owner" style={{
                  borderColor: selectedZone.owner_color || 'var(--parchment-dk)',
                }}>
                  {selectedZone.owner_clan_name || 'Neutral'}
                </span>
              </div>
              <div className="deploy-target-meta">
                Tropas: <strong>{Number(selectedZone.total_armies || 0).toLocaleString()}</strong>
                {' \u00b7 '}
                Valor: <strong>{selectedZone.value || selectedZone.value_score || '?'}</strong>
              </div>
            </div>

            {/* Recommendation */}
            <div className="advice-text" style={{ borderLeftColor: 'var(--gold)' }}>
              Sugerencia: empieza con <strong>{suggestedAmount}</strong> tropas para reforzar sin vaciar tu balance.
            </div>

            {/* Deploy form */}
            <form onSubmit={deployArmies} style={{ display: 'flex', flexDirection: 'column', gap: '.6rem' }}>
              <div className="create-form">
                <input
                  type="number"
                  min="1"
                  max={maxAvailable}
                  value={safeAmount}
                  onChange={(e) => applyAmount(e.target.value)}
                  style={{ textAlign: 'center', fontWeight: 700, fontSize: '1rem' }}
                />
                <button type="button" onClick={() => applyAmount(maxAvailable)}>MAX</button>
              </div>

              <input
                type="range"
                min="1"
                max={maxAvailable}
                value={safeAmount}
                onChange={(e) => applyAmount(e.target.value)}
                className="deploy-range"
              />

              <div className="deploy-chips">
                {[1, 3, 5, 10].map((q) => (
                  <button
                    key={q}
                    type="button"
                    className={`deploy-chip ${safeAmount === Math.min(q, maxAvailable) ? 'deploy-chip-active' : ''}`}
                    onClick={() => applyAmount(q)}
                  >
                    +{q}
                  </button>
                ))}
                <button
                  type="button"
                  className="deploy-chip deploy-chip-active"
                  onClick={() => applyAmount(suggestedAmount)}
                >
                  Sugerido
                </button>
              </div>

              <button
                type="submit"
                className="btn-attack"
                style={{ background: 'linear-gradient(180deg, var(--army-green) 0%, #1a4a1a 100%)', borderColor: '#145a14' }}
                disabled={loading || !balance?.armies_available}
              >
                {loading ? 'Desplegando...' : `\uD83D\uDEA9 Desplegar ${safeAmount} tropas`}
              </button>
            </form>
          </>
        )}

        {error && <div className="error-msg">{error}</div>}
        {success && <div style={{ color: 'var(--army-green)', fontSize: '.82rem', fontStyle: 'italic', padding: '.3rem .5rem', background: 'rgba(45,90,39,0.1)', borderLeft: '3px solid var(--army-green)', borderRadius: '2px' }}>{success}</div>}
      </div>
    </div>
  )
}
