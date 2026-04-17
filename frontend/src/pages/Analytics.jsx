import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  getTopStepsMonth,
  getTopRainyDays,
  getTopBadAir,
  getAntiCheatRejects,
} from '../api/analiticas'

const TABS = [
  { id: 'steps',  label: 'Top pasos (30d)' },
  { id: 'rain',   label: 'Top lluvia' },
  { id: 'air',    label: 'Top mala calidad aire' },
  { id: 'cheat',  label: 'Rechazos anti-trampa' },
]

const FETCHERS = {
  steps: () => getTopStepsMonth(10),
  rain:  () => getTopRainyDays(10),
  air:   () => getTopBadAir(10),
  cheat: () => getAntiCheatRejects(50),
}

export default function Analytics() {
  const [tab, setTab] = useState('steps')
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    let alive = true
    setLoading(true); setError(null)
    FETCHERS[tab]()
      .then(data => { if (alive) setRows(Array.isArray(data) ? data : []) })
      .catch(err => { if (alive) setError(err?.response?.data?.detail || err.message) })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [tab])

  const columns = rows.length > 0 ? Object.keys(rows[0]) : []

  return (
    <div style={{ padding: '1.5rem', maxWidth: 960, margin: '0 auto', fontFamily: 'system-ui' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1 style={{ margin: 0 }}>CloudRISK · Analytics</h1>
        <Link to="/" style={{ color: '#6ea8ff' }}>&larr; Volver al mapa</Link>
      </div>

      <nav style={{ display: 'flex', gap: 8, marginTop: 16, flexWrap: 'wrap' }}>
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            style={{
              padding: '0.5rem 1rem',
              borderRadius: 8,
              border: '1px solid #2e3a55',
              background: tab === t.id ? '#2e3a55' : 'transparent',
              color: '#e7ecf3',
              cursor: 'pointer',
            }}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <section style={{ marginTop: 24 }}>
        {loading && <p>Cargando…</p>}
        {error && <p style={{ color: '#ff7a7a' }}>Error: {error}</p>}
        {!loading && !error && rows.length === 0 && (
          <p style={{ opacity: 0.6 }}>
            Sin datos todavía. El pipeline Dataflow todavía no ha escrito registros
            en BigQuery, o las credenciales de BigQuery no están disponibles.
          </p>
        )}
        {!loading && !error && rows.length > 0 && (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {columns.map(c => (
                  <th key={c} style={{ textAlign: 'left', padding: 8, borderBottom: '1px solid #2e3a55' }}>
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i}>
                  {columns.map(c => (
                    <td key={c} style={{ padding: 8, borderBottom: '1px solid #1a2233' }}>
                      {formatCell(r[c])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  )
}

function formatCell(v) {
  if (v === null || v === undefined) return '—'
  if (typeof v === 'number') return Number.isInteger(v) ? v : v.toFixed(2)
  return String(v)
}
