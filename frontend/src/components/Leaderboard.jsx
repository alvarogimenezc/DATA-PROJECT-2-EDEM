import { useEffect, useState } from 'react'
import api from '../api/client'

export default function Leaderboard({ onClose }) {
  const [players, setPlayers] = useState([])
  const [tab, setTab] = useState('armies') // armies | deployed | steps

  useEffect(() => {
    // Fetch clans as proxy for leaderboard (players grouped by clan)
    api.get('/api/v1/clans').then(r => {
      const clans = r.data.sort((a, b) => (b.total_armies || 0) - (a.total_armies || 0))
      setPlayers(clans)
    }).catch(() => {})
  }, [])

  const medals = ['gold', 'silver', 'bronze']

  return (
    <div className="panel">
      <div className="panel-header">
        <h2>&#127942; Leaderboard</h2>
        <button onClick={onClose}>&#10005;</button>
      </div>
      <div className="panel-body">
        <div className="lb-tabs">
          <button className={tab === 'armies' ? 'active' : ''} onClick={() => setTab('armies')}>
            Armies
          </button>
          <button className={tab === 'territory' ? 'active' : ''} onClick={() => setTab('territory')}>
            Territory
          </button>
        </div>

        <div className="lb-list">
          {players.map((clan, idx) => (
            <div key={clan.id} className={`lb-item ${idx < 3 ? 'lb-top' : ''}`}>
              <span className={`lb-rank ${idx < 3 ? `lb-${medals[idx]}` : ''}`}>
                {idx < 3 ? ['\uD83E\uDD47', '\uD83E\uDD48', '\uD83E\uDD49'][idx] : `#${idx + 1}`}
              </span>
              <span style={{ color: clan.color || '#fff' }} className="lb-color">{'\u25A0'}</span>
              <span className="lb-name">{clan.name}</span>
              <span className="lb-members">{'\uD83D\uDC51'}{clan.member_count}</span>
              <span className="lb-score">{'\u2694\uFE0F'}{(clan.total_armies || clan.total_power || 0).toLocaleString()}</span>
            </div>
          ))}
          {players.length === 0 && (
            <p className="empty-msg">No clans yet.</p>
          )}
        </div>
      </div>
    </div>
  )
}
