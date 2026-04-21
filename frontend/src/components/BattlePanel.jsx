import { useEffect, useState, useCallback } from 'react'
import api from '../api/client'
import { useAuth } from '../contexts/AuthContext'


function rollDice(attackerPower, defenderPower) {
=======
/**
 * Simulates a Risk-style dice roll with animation.
 * Returns { attackDice: number[], defenseDice: number[], result: 'attacker'|'defender' }
 */

  const atkCount = Math.min(3, Math.max(1, Math.ceil(attackerPower / 100)))
  const defCount = Math.min(2, Math.max(1, Math.ceil(defenderPower / 100)))
  const atkDice = Array.from({ length: atkCount }, () => Math.floor(Math.random() * 6) + 1)
    .sort((a, b) => b - a)
  const defDice = Array.from({ length: defCount }, () => Math.floor(Math.random() * 6) + 1)
    .sort((a, b) => b - a)

  let atkWins = 0
  let defWins = 0
  const pairs = Math.min(atkDice.length, defDice.length)
  for (let i = 0; i < pairs; i++) {
    if (atkDice[i] > defDice[i]) atkWins++
    else defWins++
  }

  const powerRatio = attackerPower / Math.max(1, defenderPower)
  const result = powerRatio > 1.5 ? 'attacker'
    : powerRatio < 0.7 ? 'defender'
    : atkWins >= defWins ? 'attacker' : 'defender'

  return { attackDice: atkDice, defenseDice: defDice, result }
}

function DiceDisplay({ attackDice, defenseDice, result, rolling, landed }) {
  const [faces, setFaces] = useState({ atk: attackDice, def: defenseDice })

  useEffect(() => {
    if (!rolling) {
      setFaces({ atk: attackDice, def: defenseDice })
      return
    }
    const interval = setInterval(() => {
      setFaces({
        atk: attackDice.map(() => Math.floor(Math.random() * 6) + 1),
        def: defenseDice.map(() => Math.floor(Math.random() * 6) + 1),
      })
    }, 100)
    return () => clearInterval(interval)
  }, [rolling, attackDice, defenseDice])

  return (
    <div>
      <div className="dice-container">
        <div className="dice-group dice-group-atk">
          <div className="dice-group-label">Atacante</div>
          <div className="dice-row">
            {faces.atk.map((val, i) => (
              <div key={i}
                className={`die die-atk ${rolling ? 'rolling' : landed ? 'landing' : ''}`}
                style={{ animationDelay: `${i * 0.12}s` }}>
                {val}
              </div>
            ))}
          </div>
        </div>
        <div className="dice-group dice-group-def">
          <div className="dice-group-label">Defensor</div>
          <div className="dice-row">
            {faces.def.map((val, i) => (
              <div key={i}
                className={`die die-def ${rolling ? 'rolling' : landed ? 'landing' : ''}`}
                style={{ animationDelay: `${i * 0.12 + 0.15}s` }}>
                {val}
              </div>
            ))}
          </div>
        </div>
      </div>
      {!rolling && result && (
        <div className={`dice-result ${result === 'attacker' ? 'atk-wins' : 'def-wins'}`}>
          {result === 'attacker'

            ? '⚔️ Victoria del Atacante!'
            : '🛡️ El Defensor Resiste!'}

        </div>
      )}
    </div>
  )
}

export default function BattlePanel({ onClose, currentZone }) {
  const { user } = useAuth()
  const [battles, setBattles] = useState([])
  const [advice, setAdvice] = useState({})

  const [diceState, setDiceState] = useState({})

  const [error, setError] = useState('')

  useEffect(() => {
    api.get('/api/v1/battles/').then(r => setBattles(r.data)).catch(() => {})
  }, [])

  const startBattle = () => {
    if (!currentZone) return
    setError('Para atacar, marcha al territorio en el mapa y usa el botón de ataque desde allí.')
  }

  const getAdvice = async (battleId) => {
    try {
      const res = await api.get(`/api/v1/battles/${battleId}/advice`)
      setAdvice(a => ({ ...a, [battleId]: res.data.advice }))
    } catch {

      setAdvice(a => ({ ...a, [battleId]: 'El consejero no está disponible.' }))

    }
  }

  const handleRollDice = useCallback((battle) => {


    const atkCount = Math.min(3, Math.max(1, Math.ceil(battle.attacker_power / 100)))
    const defCount = Math.min(2, Math.max(1, Math.ceil(battle.defender_power / 100)))
    setDiceState(prev => ({
      ...prev,
      [battle.id]: {
        attackDice: Array(atkCount).fill(0),
        defenseDice: Array(defCount).fill(0),
        result: null,
        rolling: true,
        landed: false,
      }
    }))


    setTimeout(() => {
      const result = rollDice(battle.attacker_power, battle.defender_power)
      setDiceState(prev => ({
        ...prev,
        [battle.id]: { ...result, rolling: false, landed: true }
      }))
      
      api.post(`/api/v1/battles/${battle.id}/resolve`).catch(() => {})

      setTimeout(() => {
        setDiceState(prev => ({
          ...prev,
          [battle.id]: { ...prev[battle.id], landed: false }
        }))
      }, 500)
    }, 2000)
  }, [])

  const canAttack =
    currentZone &&
    currentZone.owner_clan_id !== user?.clan_id &&
    user?.clan_id

  return (
    <div className="panel">
      <div className="panel-header">
    
        <h2>⚔️ Consejo de Guerra</h2>
        <button onClick={onClose}>✕</button>

      </div>
      <div className="panel-body">
        {canAttack && (
          <button className="btn-attack" onClick={startBattle}>
            Lanzar Ofensiva: {currentZone.name}
          </button>
        )}
        {!currentZone && (
          <p className="empty-msg">Marcha hacia un territorio para atacarlo.</p>
        )}

        {error && <div className="error-msg">{error}</div>}

        {battles.length === 0 ? (
          <p className="empty-msg">No hay batallas activas en el frente.</p>
        ) : (
          <div className="battle-list">
            {battles.map(b => (
              <div key={b.id} className="battle-item">
                <div className="battle-info">

                  <span>🗺️ Zona {b.zone_id.slice(0, 8)}…</span>
                  <div className="battle-powers">
                    <span className="power-atk">⚔️{b.attacker_power}</span>
                    <span className="power-vs">vs</span>
                    <span className="power-def">🛡️{b.defender_power}</span>
                  </div>
                </div>

                {diceState[b.id] && (
                  <DiceDisplay
                    attackDice={diceState[b.id].attackDice}
                    defenseDice={diceState[b.id].defenseDice}
                    result={diceState[b.id].result}
                    rolling={diceState[b.id].rolling}
                    landed={diceState[b.id].landed}
                  />
                )}

                <div style={{ display: 'flex', gap: '.4rem', flexWrap: 'wrap' }}>
                  {!diceState[b.id] && (
                    <button onClick={() => handleRollDice(b)}>
                      {'\uD83C\uDFB2'} Tirar Dados
                    </button>
                  )}
                  {diceState[b.id] && !diceState[b.id].rolling && (
                    <button onClick={() => handleRollDice(b)}>
                      {'\uD83C\uDFB2'} Volver a Tirar
                    </button>
                  )}
                  <button onClick={() => getAdvice(b.id)}>
                    {'\uD83E\uDDD9'} Pedir Consejo
                  </button>
                </div>

                {advice[b.id] && <p className="advice-text">{advice[b.id]}</p>}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
