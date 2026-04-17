import { useCallback, useEffect, useMemo, useState } from 'react'
import '../styles/tactical-ui.css'

const PIPS = {
  1: [[32, 32]],
  2: [[16, 16], [48, 48]],
  3: [[16, 16], [32, 32], [48, 48]],
  4: [[16, 16], [48, 16], [16, 48], [48, 48]],
  5: [[16, 16], [48, 16], [32, 32], [16, 48], [48, 48]],
  6: [[16, 14], [48, 14], [16, 32], [48, 32], [16, 50], [48, 50]],
}

function randomDie() {
  return Math.floor(Math.random() * 6) + 1
}

function Die({ value, tone, rolling = false }) {
  return (
    <div className={`cq-die cq-die--${tone} ${rolling ? 'is-rolling' : ''}`}>
      {(PIPS[value] || PIPS[1]).map(([left, top], index) => (
        <span
          key={`${value}-${index}`}
          className="cq-pip"
          style={{ left: `${left}px`, top: `${top}px` }}
        />
      ))}
    </div>
  )
}

export default function DiceRoll({ attackerCount, defenderCount, onResult, onClose }) {
  const [phase, setPhase] = useState('ready')
  const [rollFrame, setRollFrame] = useState(0)
  const [attackerDice, setAttackerDice] = useState([])
  const [defenderDice, setDefenderDice] = useState([])
  const [result, setResult] = useState(null)

  const attackDiceCount = useMemo(() => Math.max(1, Math.min(3, attackerCount - 1)), [attackerCount])
  const defendDiceCount = useMemo(() => Math.max(1, Math.min(2, defenderCount)), [defenderCount])

  useEffect(() => {
    if (phase !== 'rolling') return

    if (rollFrame >= 10) {
      const attackRolls = Array.from({ length: attackDiceCount }, randomDie).sort((a, b) => b - a)
      const defendRolls = Array.from({ length: defendDiceCount }, randomDie).sort((a, b) => b - a)

      let attackerLosses = 0
      let defenderLosses = 0
      const comparisons = Math.min(attackRolls.length, defendRolls.length)

      for (let i = 0; i < comparisons; i += 1) {
        if (attackRolls[i] > defendRolls[i]) defenderLosses += 1
        else attackerLosses += 1
      }

      setAttackerDice(attackRolls)
      setDefenderDice(defendRolls)
      setResult({
        attackerLosses,
        defenderLosses,
        attackerDice: attackRolls,
        defenderDice: defendRolls,
      })
      setPhase('result')
      return
    }

    const timer = window.setTimeout(() => {
      setAttackerDice(Array.from({ length: attackDiceCount }, randomDie))
      setDefenderDice(Array.from({ length: defendDiceCount }, randomDie))
      setRollFrame((current) => current + 1)
    }, 90)

    return () => window.clearTimeout(timer)
  }, [attackDiceCount, defendDiceCount, phase, rollFrame])

  const handleRoll = useCallback(() => {
    if (attackerCount <= 1 || defenderCount <= 0) return
    setResult(null)
    setRollFrame(0)
    setPhase('rolling')
  }, [attackerCount, defenderCount])

  const handleConfirm = useCallback(() => {
    if (result) onResult?.(result)
    onClose?.()
  }, [onClose, onResult, result])

  return (
    <div className="cq-dice-overlay" onClick={(event) => event.target === event.currentTarget && onClose?.()}>
      <div className="cq-dice-modal cq-glass">
        <div className="cq-dice-modal__header">
          <div>
            <span className="cq-panel__eyebrow">Combate por dados</span>
            <h2 style={{ margin: 0 }}>Resolución estilo Risk</h2>
          </div>
          <button type="button" className="cq-panel__close" onClick={onClose}>
            ✕
          </button>
        </div>

        <div className="cq-dice-modal__body">
          <div className="cq-dice-lanes">
            <div className="cq-dice-lane">
              <span className="cq-dice-lane__label">Atacante</span>
              <div className="cq-dice-lane__count" style={{ color: 'var(--cq-danger)' }}>
                {attackerCount}
              </div>
              <div className="cq-dice-row">
                {(phase === 'ready' ? Array.from({ length: attackDiceCount }, () => 1) : attackerDice).map((die, index) => (
                  <Die key={`a-${index}`} value={die} tone="attack" rolling={phase === 'rolling'} />
                ))}
              </div>
            </div>

            <div className="cq-dice-lane">
              <span className="cq-dice-lane__label">Defensor</span>
              <div className="cq-dice-lane__count" style={{ color: 'var(--cq-accent-2)' }}>
                {defenderCount}
              </div>
              <div className="cq-dice-row">
                {(phase === 'ready' ? Array.from({ length: defendDiceCount }, () => 1) : defenderDice).map((die, index) => (
                  <Die key={`d-${index}`} value={die} tone="defend" rolling={phase === 'rolling'} />
                ))}
              </div>
            </div>
          </div>

          {result && (
            <div className="cq-dice-result">
              {result.defenderLosses > 0 && (
                <div className="cq-result-line cq-result-line--win">
                  El defensor pierde {result.defenderLosses} {result.defenderLosses === 1 ? 'unidad' : 'unidades'}.
                </div>
              )}
              {result.attackerLosses > 0 && (
                <div className="cq-result-line cq-result-line--loss">
                  El atacante pierde {result.attackerLosses} {result.attackerLosses === 1 ? 'unidad' : 'unidades'}.
                </div>
              )}
              <div className="cq-dice-summary">
                <div className="cq-help">
                  Dados atacante: <strong>{result.attackerDice.join(' · ')}</strong>
                </div>
                <div className="cq-help">
                  Dados defensor: <strong>{result.defenderDice.join(' · ')}</strong>
                </div>
              </div>
            </div>
          )}

          <div className="cq-inline-row">
            {phase !== 'rolling' && (
              <button type="button" className="cq-danger-btn" onClick={handleRoll}>
                🎲 Lanzar dados
              </button>
            )}
            {phase === 'result' && (
              <button type="button" className="cq-primary-btn" onClick={handleConfirm}>
                Confirmar resultado
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
