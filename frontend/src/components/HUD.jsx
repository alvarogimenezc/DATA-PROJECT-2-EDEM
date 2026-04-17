const VIEW_MODES = [
  { key: 'control', label: 'Control' },
  { key: 'pressure', label: 'Presi\u00f3n' },
  { key: 'economy', label: 'Econom\u00eda' },
]

export default function HUD({
  user,
  currentZone,
  activeMode = 'control',
  onChangeMode,
  onOpenClans,
  onOpenLeaderboard,
  onOpenSettings,
  onLogout,
  activeBattles = 0,
}) {
  if (!user) return null

  return (
    <div className="hud-frame">
      <div className="hud">
        <div className="hud-left">
          <span className="hud-name">Cmdte. {user.name}</span>
          <span className="hud-level">Rango {user.level ?? 1}</span>
        </div>

        <div className="hud-divider" />

        <div className="hud-stats">
          <div className="hud-stat" title="Ej&eacute;rcitos disponibles">
            <span>{'\u2694\uFE0F'}</span>
            <span className="hud-stat-value">{Number(user.armies || user.power_points || 0).toLocaleString()}</span>
          </div>
          <div className="hud-stat" title="Tesoro">
            <span>{'\uD83E\uDE99'}</span>
            <span className="hud-stat-value">{Number(user.gold || 0).toLocaleString()}</span>
          </div>
          <div className="hud-stat" title="Pasos de Marcha">
            <span>{'\uD83E\uDDB6'}</span>
            <span className="hud-stat-value">{Number(user.steps_total || 0).toLocaleString()}</span>
          </div>
          {activeBattles > 0 && (
            <div className="hud-stat" title="Batallas activas">
              <span>{'\uD83D\uDD25'}</span>
              <span className="hud-stat-value">{activeBattles}</span>
            </div>
          )}
        </div>

        {currentZone && (
          <>
            <div className="hud-divider" />
            <div className="hud-zone">
              {'\uD83D\uDDFA\uFE0F'} {currentZone.name}
              {currentZone.owner_clan_id
                ? ` \u00b7 ${currentZone.owner_clan_name || 'Conquistado'}`
                : ' \u00b7 Tierra de Nadie'}
            </div>
          </>
        )}

        <div className="hud-divider" />

        <div className="hud-modes">
          {VIEW_MODES.map((mode) => (
            <button
              key={mode.key}
              className={`hud-mode-btn ${activeMode === mode.key ? 'hud-mode-active' : ''}`}
              onClick={() => onChangeMode?.(mode.key)}
            >
              {mode.label}
            </button>
          ))}
        </div>

        <div className="hud-actions">
          <button className="hud-action-btn" onClick={onOpenClans} title="Facciones">
            {'\uD83C\uDFF0'}
          </button>
          <button className="hud-action-btn" onClick={onOpenLeaderboard} title="Ranking">
            {'\uD83C\uDFC6'}
          </button>
          <button className="hud-action-btn" onClick={onOpenSettings} title="Configuración">⚙️</button>
          <button className="hud-logout" onClick={onLogout} title="Retirada">
            {'\u23FB'}
          </button>
        </div>
      </div>
    </div>
  )
}
