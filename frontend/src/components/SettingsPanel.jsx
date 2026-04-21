import { useState, useEffect, useRef } from 'react'
import { useAuth } from '../contexts/AuthContext'

const ZOOM_KEY = 'cloudrisk_zoom'

export default function SettingsPanel({ onClose }) {
  const { user, logout } = useAuth()
  const [notifStatus, setNotifStatus] = useState(
    typeof Notification !== 'undefined' ? Notification.permission : 'unsupported'
  )
  const [zoom, setZoom] = useState(() => localStorage.getItem(ZOOM_KEY) || '13')
  const zoomMounted = useRef(false)

<<<<<<< Front_Ricardo
=======
  // Skip writing on mount — the value was just read from localStorage
>>>>>>> main
  useEffect(() => {
    if (!zoomMounted.current) { zoomMounted.current = true; return }
    localStorage.setItem(ZOOM_KEY, zoom)
  }, [zoom])

  const handleNotifToggle = async () => {
    if (typeof Notification === 'undefined') return
    if (Notification.permission === 'granted') return
    const result = await Notification.requestPermission()
    setNotifStatus(result)
  }

  return (
    <div className="panel">
      <div className="panel-header">
        <h2>⚙️ CONFIGURACIÓN</h2>
        <button onClick={onClose}>✕</button>
      </div>
      <div className="panel-body">
<<<<<<< Front_Ricardo
=======
        {/* User profile card */}
>>>>>>> main
        {user && (
          <div className="clan-item" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: '.35rem' }}>
            <span style={{ fontFamily: "'Cinzel', serif", fontWeight: 700, fontSize: '.9rem', color: 'var(--ink)' }}>
              Cmdte. {user.name}
            </span>
            <span style={{ fontSize: '.8rem', color: 'var(--ink-dim)' }}>
              Rango {user.level ?? 1} · {user.clan_name ? user.clan_name : 'Sin facción'}
            </span>
            <span style={{ fontSize: '.8rem', color: 'var(--ink-dim)' }}>
<<<<<<< Front_Ricardo
              👣 Pasos totales: {Number(user.steps_total || 0).toLocaleString()}
=======
              🦶 Pasos totales: {Number(user.steps_total || 0).toLocaleString()}
>>>>>>> main
            </span>
          </div>
        )}

<<<<<<< Front_Ricardo
=======
        {/* Notifications */}
>>>>>>> main
        <div className="clan-item" style={{ justifyContent: 'space-between' }}>
          <span style={{ fontSize: '.85rem', color: 'var(--ink)' }}>🔔 Notificaciones</span>
          {notifStatus === 'unsupported' ? (
            <span style={{ fontSize: '.75rem', color: 'var(--ink-dim)' }}>No soportado</span>
          ) : notifStatus === 'granted' ? (
            <span style={{ fontSize: '.75rem', color: 'var(--ink-dim)' }}>Activadas</span>
          ) : (
            <button onClick={handleNotifToggle}>Activar</button>
          )}
        </div>

<<<<<<< Front_Ricardo
=======
        {/* Map zoom preference */}
>>>>>>> main
        <div className="clan-item" style={{ justifyContent: 'space-between' }}>
          <span style={{ fontSize: '.85rem', color: 'var(--ink)' }}>🗺️ Zoom predeterminado</span>
          <select
            value={zoom}
            onChange={e => setZoom(e.target.value)}
            style={{
              background: 'rgba(250,243,227,0.7)',
              border: '2px solid var(--parchment-dk)',
              borderRadius: '3px',
              padding: '.3rem .5rem',
              color: 'var(--ink)',
              fontFamily: "'IM Fell English', serif",
              fontSize: '.85rem',
              cursor: 'pointer',
            }}
          >
<<<<<<< Front_Ricardo
            <option value="12">12 – Amplio</option>
            <option value="13">13 – Normal</option>
            <option value="14">14 – Cercano</option>
          </select>
        </div>

=======
            <option value="12">12 — Amplio</option>
            <option value="13">13 — Normal</option>
            <option value="14">14 — Cercano</option>
          </select>
        </div>

        {/* App info */}
>>>>>>> main
        <div style={{ fontSize: '.75rem', color: 'var(--ink-dim)', textAlign: 'center', lineHeight: 1.6, marginTop: '.25rem' }}>
          CloudRISK · Valencia, España
          <br />
          Estrategia de geolocalización
        </div>

<<<<<<< Front_Ricardo
        <button className="btn-danger" onClick={logout} style={{ alignSelf: 'stretch', textAlign: 'center' }}>
          ↻ Cerrar sesión
=======
        {/* Logout */}
        <button className="btn-danger" onClick={logout} style={{ alignSelf: 'stretch', textAlign: 'center' }}>
          ⏻ Cerrar sesión
>>>>>>> main
        </button>
      </div>
    </div>
  )
}
