import { useEffect, useState } from 'react'
import api from '../api/client'
import { useAuth } from '../contexts/AuthContext'

export default function FortifyPanel({ onClose }) {
  const { user } = useAuth()
  const [locations, setLocations] = useState([])
  const [fromZone, setFromZone] = useState(null)
  const [toZone, setToZone] = useState(null)
  const [amount, setAmount] = useState(1)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  useEffect(() => {
    api.get('/api/v1/state/locations')
      .then(r => {
        const myZones = r.data.filter(loc => {
          const garrisons = loc.garrisons || {}
          return garrisons[user?.id] && garrisons[user.id].armies > 0
        })
        setLocations(myZones)
      })
      .catch(() => {})
  }, [user?.id])

  const getMyArmies = (loc) => {
    const g = loc?.garrisons?.[user?.id]
    return g ? g.armies : 0
  }

  const handleFortify = async () => {
    if (!fromZone || !toZone || amount <= 0) return
    setError('')
    setSuccess('')
    try {
      await api.post('/api/v1/armies/fortify', {
        from_location_id: fromZone.location_id || fromZone.id,
        to_location_id: toZone.location_id || toZone.id,
        amount,
      })
      setSuccess(`${amount} tropas movidas de ${fromZone.name} a ${toZone.name}`)
      setFromZone(null)
      setToZone(null)
      setAmount(1)
    } catch (err) {
      setError(err.response?.data?.detail || 'No se pudieron mover las tropas')
    }
  }

  const maxMovable = fromZone ? Math.max(0, getMyArmies(fromZone) - 1) : 0

  return (
    <div className="panel">
      <div className="panel-header">
        <h2>🛡️ Fortificar</h2>
        <button onClick={onClose}>✕</button>
      </div>
      <div className="panel-body">
        <p className="empty-msg" style={{ textAlign: 'left' }}>
          Mueve tropas entre tus propios territorios.
        </p>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '.5rem' }}>
          <label style={{ fontWeight: 700, fontSize: '.82rem' }}>Origen:</label>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '.3rem' }}>
            {locations.map(loc => (
              <button
                key={loc.location_id || loc.id}
                className="clan-item"
                style={{
                  cursor: 'pointer', fontSize: '.78rem',
                  borderColor: fromZone === loc ? 'var(--leather)' : undefined,
                }}
                onClick={() => { setFromZone(loc); setToZone(null); setAmount(1) }}
              >
                {loc.name} ({getMyArmies(loc)})
              </button>
            ))}
            {locations.length === 0 && (
              <p className="empty-msg">Sin territorios con tus tropas.</p>
            )}
          </div>
        </div>

        {fromZone && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '.5rem' }}>
            <label style={{ fontWeight: 700, fontSize: '.82rem' }}>Destino:</label>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '.3rem' }}>
              {locations
                .filter(loc => loc !== fromZone)
                .map(loc => (
                  <button
                    key={loc.location_id || loc.id}
                    className="clan-item"
                    style={{
                      cursor: 'pointer', fontSize: '.78rem',
                      borderColor: toZone === loc ? 'var(--leather)' : undefined,
                    }}
                    onClick={() => setToZone(loc)}
                  >
                    {loc.name} ({getMyArmies(loc)})
                  </button>
                ))}
            </div>
          </div>
        )}

        {fromZone && toZone && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '.5rem' }}>
            <div className="create-form">
              <input
                type="number"
                min="1"
                max={maxMovable}
                value={amount}
                onChange={e => setAmount(Math.max(1, Math.min(maxMovable, parseInt(e.target.value) || 1)))}
              />
              <button type="button" onClick={() => setAmount(maxMovable)}>MAX</button>
            </div>
            <button className="btn-attack" onClick={handleFortify}>
              Mover {amount} tropas
            </button>
          </div>
        )}

        {error && <div className="error-msg">{error}</div>}
        {success && <div style={{ color: 'var(--army-green)', fontSize: '.82rem', fontStyle: 'italic' }}>{success}</div>}
      </div>
    </div>
  )
}
