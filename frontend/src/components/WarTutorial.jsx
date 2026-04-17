import { useState } from 'react'

const STEPS = [
  {
    title: 'Bienvenido a la Guerra',
    icon: '\u2694\uFE0F',
    body: (
      <>
        <p>
          <strong>CloudRISK</strong> es un juego de estrategia geolocalizado.
          Camina por la ciudad, acumula poder con tus pasos y conquista territorios reales
          sobre el mapa, igual que en el cl&aacute;sico juego de mesa <em>Risk</em>.
        </p>
        <div className="tutorial-step-icon">{'\uD83C\uDF0D'}</div>
        <p>
          Tu misi&oacute;n: dominar el mapa con tu facci&oacute;n. Cada paso cuenta.
          Cada territorio importa.
        </p>
      </>
    ),
  },
  {
    title: 'El Mapa de Conquista',
    icon: '\uD83D\uDDFA\uFE0F',
    body: (
      <>
        <p>
          El mapa muestra <strong>territorios reales</strong> de la ciudad. Cada zona tiene
          un color que indica qu&eacute; facci&oacute;n la controla:
        </p>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', margin: '0.6rem 0' }}>
          {[
            { color: '#c41e3a', label: 'Facci\u00f3n Roja' },
            { color: '#1e4d8c', label: 'Facci\u00f3n Azul' },
            { color: '#2d5a27', label: 'Facci\u00f3n Verde' },
            { color: '#c4a000', label: 'Facci\u00f3n Dorada' },
          ].map(f => (
            <div key={f.color} style={{
              display: 'flex', alignItems: 'center', gap: '0.3rem',
              padding: '0.25rem 0.5rem', background: 'rgba(250,243,227,0.5)',
              border: `2px solid ${f.color}`, borderRadius: '3px', fontSize: '0.8rem',
            }}>
              <div style={{
                width: 14, height: 18, backgroundColor: f.color, flexShrink: 0,
                clipPath: 'polygon(0 0, 100% 0, 100% 70%, 50% 100%, 0 70%)',
              }} />
              {f.label}
            </div>
          ))}
        </div>
        <p>
          Las zonas sin color son <strong>Tierra de Nadie</strong> &mdash; listas para ser conquistadas.
          Pulsa sobre cualquier territorio para ver su ficha de estado.
        </p>
      </>
    ),
  },
  {
    title: 'Marcha y Poder',
    icon: '\uD83E\uDDB6',
    body: (
      <>
        <p>
          Tu <strong>poder militar</strong> se gana caminando. Cada <strong>100 pasos</strong> reales
          se convierten en <strong>1 punto de poder</strong>.
        </p>
        <div className="tutorial-step-icon">{'\u2694\uFE0F'}</div>
        <p>
          El poder determina tu fuerza en batalla. Cuanto m&aacute;s camines,
          m&aacute;s temible ser&aacute; tu ej&eacute;rcito. La barra superior muestra tus estad&iacute;sticas:
          poder, tesoro y pasos acumulados.
        </p>
      </>
    ),
  },
  {
    title: 'Facciones y Alianzas',
    icon: '\u2690',
    body: (
      <>
        <p>
          No puedes conquistar solo. <strong>Funda una facci&oacute;n</strong> o
          {' '}<strong>jura lealtad</strong> a una existente.
        </p>
        <div className="tutorial-step-icon">{'\uD83D\uDC51'}</div>
        <p>
          El poder de todos los miembros de tu facci&oacute;n se suma para las batallas.
          Usa el bot&oacute;n <strong>&ldquo;Facciones&rdquo;</strong> en la parte inferior
          del mapa para gestionar tu alianza.
        </p>
      </>
    ),
  },
  {
    title: 'Batalla y Dados',
    icon: '\uD83C\uDFB2',
    body: (
      <>
        <p>
          Cuando est&eacute;s dentro de un territorio enemigo, pulsa
          {' '}<strong>&ldquo;Lanzar Ofensiva&rdquo;</strong> desde el Consejo de Guerra.
        </p>
        <div className="tutorial-step-icon">{'\uD83C\uDFB2'}</div>
        <p>
          Las batallas se resuelven con <strong>dados al estilo Risk</strong>:
          el atacante tira hasta 3 dados rojos, el defensor hasta 2 dados azules.
          Se comparan de mayor a menor. &iexcl;Que la estrategia y la suerte est&eacute;n de tu lado!
        </p>
        <p>
          Tambi&eacute;n puedes <strong>pedir consejo</strong> a tu asesor de guerra antes de atacar.
        </p>
      </>
    ),
  },
  {
    title: '\u00A1A la Conquista!',
    icon: '\uD83C\uDFC6',
    body: (
      <>
        <p>
          Ya conoces las reglas del campo de batalla. Ahora sal ah&iacute; fuera,
          camina, re&uacute;ne a tu facci&oacute;n y conquista la ciudad.
        </p>
        <div className="tutorial-step-icon">{'\u2694\uFE0F\uD83C\uDF0D\uD83C\uDFC6'}</div>
        <p style={{ fontStyle: 'italic', textAlign: 'center', color: '#6b5a4e' }}>
          &ldquo;La victoria pertenece a quien camina m&aacute;s lejos.&rdquo;
        </p>
      </>
    ),
  },
]

export default function WarTutorial({ onComplete }) {
  const [step, setStep] = useState(0)
  const current = STEPS[step]
  const isLast = step === STEPS.length - 1
  const isFirst = step === 0

  return (
    <div className="tutorial-overlay">
      <div className="tutorial-card">
        <div className="tutorial-title">Manual de Guerra</div>
        <div className="tutorial-subtitle">Briefing para nuevos comandantes</div>

        {/* Progress dots */}
        <div className="tutorial-progress">
          {STEPS.map((_, i) => (
            <div
              key={i}
              className={`tutorial-dot ${i === step ? 'active' : i < step ? 'completed' : ''}`}
            />
          ))}
        </div>

        {/* Current step */}
        <div className="tutorial-step" key={step}>
          <div className="tutorial-step-header">
            <div className="tutorial-step-number">{step + 1}</div>
            <div className="tutorial-step-title">
              {current.icon} {current.title}
            </div>
          </div>
          <div className="tutorial-step-body">
            {current.body}
          </div>
        </div>

        {/* Navigation */}
        <div className="tutorial-nav">
          {!isFirst ? (
            <button
              className="tutorial-btn tutorial-btn-secondary"
              onClick={() => setStep(s => s - 1)}
            >
              {'\u2190'} Retroceder
            </button>
          ) : (
            <button
              className="tutorial-btn tutorial-btn-secondary"
              onClick={onComplete}
            >
              Saltar
            </button>
          )}

          {isLast ? (
            <button className="tutorial-btn tutorial-btn-gold" onClick={onComplete}>
              {'\u2694\uFE0F'} Entrar en Batalla
            </button>
          ) : (
            <button className="tutorial-btn" onClick={() => setStep(s => s + 1)}>
              Avanzar {'\u2192'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
