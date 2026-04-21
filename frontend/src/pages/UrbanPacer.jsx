/**
 * CloudRISK — Runner CloudRISK UI con paridad completa con CloudRISK.
 * SPA con 3 estados (Login → Dashboard → Map) usando React + Tailwind +
 * Framer Motion + lucide-react + MapLibre con GeoJSON real de Valencia.
 *
 * Features:
 * - Login/Register contra backend real
 * - Tutorial interactivo de bienvenida
 * - Mapa MapLibre con 49 distritos reales de Valencia (GeoJSON)
 * - Stats reales (power, coins, steps, level)
 * - Paneles Deploy / Attack / Fortify / Walk (Marchar)
 * - WebSocket para location updates
 * - Leaderboard y misiones desde backend
 */
import React, { useState, useEffect, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import {
  Activity, Bolt, Crown, Footprints, Gift, Map as MapIcon,
  Medal, Play, Power, Target, Trophy,
  X, Zap, ChevronLeft, Flame, TrendingUp, Swords, Shield, Plus, Minus,
  BookOpen, ChevronRight, Send, ScrollText,
  // Iconos para carruseles (reemplazan emojis — monocromo, coloreable)
  Calendar, Repeat, Mountain, MessageCircle, Timer, Utensils, Pill,
  Droplet, Clock, Moon, Snowflake, Flag, Lightbulb,
  Users, MapPin, Bed, TrendingDown, Gauge,
} from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import api from '../api/client'
import useWebSocket from '../hooks/useWebSocket'
import '../styles/urban-pacer.css'

// ─────────────────────────────────────────────────────────────
// Color palette per faction
// ─────────────────────────────────────────────────────────────
const FACTION_COLORS = ['#f43f5e', '#06b6d4', '#facc15', '#a855f7', '#ff8c2a', '#5fee9a']

<<<<<<< Front_Ricardo
=======
// Single source of truth for the 4 lobby players. Used by the HUD, the bot
// overlay, SimulateBotsButton, TurnBanner, etc. Keeping it at module scope
// avoids the drift we had before (BOT_PLAYER_COLORS lacked Norte, hard-coded
// duplicates in MapView/TurnBanner/SimulateBotsButton).
>>>>>>> main
const PLAYERS = {
  'demo-player-001': { key: 'norte', name: 'Norte', color: '#f43f5e' },
  'demo-player-002': { key: 'sur',   name: 'Sur',   color: '#facc15' },
  'demo-player-003': { key: 'este',  name: 'Este',  color: '#06b6d4' },
  'demo-player-004': { key: 'oeste', name: 'Oeste', color: '#a855f7' },
}

<<<<<<< Front_Ricardo
=======
// ─────────────────────────────────────────────────────────────
// Shared turn-polling singleton — before, 4 components polled
// /api/v1/turn/ every 3 s independently (TurnBanner, ActionPanel,
// EndTurnButton, SimulateBotsButton). Now a single interval feeds
// every subscriber, cutting traffic by 4× and giving consistent
// reads across components on the same frame.
// ─────────────────────────────────────────────────────────────
>>>>>>> main
const _turnPoll = {
  data: null,
  listeners: new Set(),
  interval: null,
  ensure() {
    if (this.interval) return
    const tick = async () => {
      try {
        const r = await api.get('/api/v1/turn/')
        this.data = r.data
        this.listeners.forEach(fn => { try { fn(this.data) } catch {} })
<<<<<<< Front_Ricardo
      } catch { /* swallow */ }
=======
      } catch { /* swallow — individual components will fall back to null */ }
>>>>>>> main
    }
    tick()
    this.interval = setInterval(tick, 3000)
  },
  stopIfEmpty() {
    if (this.listeners.size === 0 && this.interval) {
      clearInterval(this.interval)
      this.interval = null
    }
  },
}

function useTurnPoll() {
  const [turn, setTurn] = useState(_turnPoll.data)
  useEffect(() => {
    setTurn(_turnPoll.data)
    _turnPoll.listeners.add(setTurn)
    _turnPoll.ensure()
    return () => {
      _turnPoll.listeners.delete(setTurn)
      _turnPoll.stopIfEmpty()
    }
  }, [])
  return turn
}
<<<<<<< Front_Ricardo

=======
>>>>>>> main
const hashColor = (seed) => {
  let h = 0
  const s = String(seed || '')
  for (let i = 0; i < s.length; i++) h = ((h << 5) - h + s.charCodeAt(i)) | 0
  return FACTION_COLORS[Math.abs(h) % FACTION_COLORS.length]
}
const getCentroid = (geom) => {
  const coords = geom.type === 'Polygon' ? geom.coordinates[0] : geom.coordinates[0][0]
  let cx = 0, cy = 0
  coords.forEach(c => { cx += c[0]; cy += c[1] })
  return [cx / coords.length, cy / coords.length]
}

// ─────────────────────────────────────────────────────────────
// Animated background — neon grid (login only)
// ─────────────────────────────────────────────────────────────
/**
 * Background Nike-style del lobby.
 *
 * Antes: blobs magenta + cyan + lima pulsando como un club, + grid
 * magenta. Muy cyberpunk pero competía visualmente con todo lo demás.
 *
 * Ahora:
 *   - Fondo base negro puro (#000)
 *   - Foto de runner Unsplash centrada, difuminada 8px + 15% opacity
 *     para que sea ambiente sin distraer
 *   - Gradiente oscuro sobre la foto para que el texto blanco siga
 *     legible sin importar dónde caiga
 *
 * Es el look de takeover editorial de Nike: producto protagonista,
 * foto motivacional de fondo, casi negro.
 */
function NeonGrid() {
  // Foto de Spencer Backman — runner al amanecer en la ciudad. Licencia
  // Unsplash libre. Se carga con ?w=1600 para no saturar y ?blur=20 CDN.
  const BG_RUNNER = 'https://images.unsplash.com/photo-1461896836934-ffe607ba8211?w=1600&q=70&auto=format&fit=crop'
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      {/* Foto ambiente de runner — muy tenue para no competir con UI */}
      <div
        className="absolute inset-0"
        style={{
          backgroundImage: `url(${BG_RUNNER})`,
          backgroundSize: 'cover',
          backgroundPosition: 'center',
          filter: 'blur(2px) grayscale(60%)',
          opacity: 0.18,
        }}
      />
      {/* Gradiente oscuro para garantizar contraste del texto blanco */}
      <div
        className="absolute inset-0"
        style={{
          background:
            'linear-gradient(180deg, rgba(0,0,0,0.85) 0%, rgba(0,0,0,0.55) 40%, rgba(0,0,0,0.85) 100%)',
        }}
      />
    </div>
  )
}

// ─────────────────────────────────────────────────────────────
// Real Player Stats Bar — shown on login screen
// Displays actual game progression, not simulated biometrics
// ─────────────────────────────────────────────────────────────
function PlayerStatsBar({ player }) {
  // Derive engaging stats from real player data
  const level = player?.level || 1
  const power = player?.power_points || 0
  const gold = player?.gold || 0
  const steps = player?.steps_total || 0
  const distKm = (steps * 0.00075).toFixed(2) // ~0.75m per step

  const s = (size, col, extra = {}) => ({
    fontSize: size, color: col, fontFamily: "'Space Grotesk', sans-serif",
    fontWeight: 900, lineHeight: 1, ...extra,
  })
  const div = <div style={{ width: 1, height: 60, background: 'rgba(255,255,255,0.1)', margin: '0 24px' }} />

  return (
    <div className="absolute inset-0 pointer-events-none overflow-hidden" style={{ zIndex: 2 }}>
      {/* Tagline */}
      <div style={{
        position: 'absolute', bottom: 152, left: '50%', transform: 'translateX(-50%)',
        display: 'flex', alignItems: 'center', gap: 10, whiteSpace: 'nowrap',
        animation: 'up-heartbeat-pink 2.4s ease-in-out infinite',
      }}>
        <span style={{ fontSize: 18, color: '#f43f5e', fontFamily: "'Space Grotesk', sans-serif",
          fontWeight: 800, letterSpacing: '0.18em', textTransform: 'uppercase',
          textShadow: '0 0 16px #f43f5e, 0 0 36px #f43f5e88' }}>
          ♥ El juego que acelera tu corazón
        </span>
      </div>

      {/* Stats bar */}
      <div style={{
        position: 'absolute', bottom: 32, left: '50%', transform: 'translateX(-50%)',
        display: 'flex', alignItems: 'center', gap: 0,
        background: 'rgba(6,7,13,0.55)', backdropFilter: 'blur(12px)',
        border: '1px solid rgba(255,255,255,0.08)', borderRadius: 20,
        padding: '14px 32px', opacity: 0.80,
      }}>
        {/* Nivel */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 100 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
            <span style={s(38, '#f43f5e')}>{level}</span>
            <span style={s(11, '#f43f5e', { fontWeight: 700, letterSpacing: '0.08em' })}>LVL</span>
          </div>
          <div style={{ fontSize: 9, color: 'rgba(255,45,146,0.7)', fontFamily: "'Space Grotesk',sans-serif",
            fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', marginTop: 2 }}>
            ★ Nivel
          </div>
        </div>

        {div}

        {/* Poder */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 110 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 3 }}>
            <span style={s(38, '#facc15')}>{power}</span>
          </div>
          <div style={{ fontSize: 9, color: 'rgba(202,255,51,0.7)', fontFamily: "'Space Grotesk',sans-serif",
            fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', marginTop: 2 }}>
            ⚡ Poder
          </div>
        </div>

        {div}

        {/* Monedas */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 100 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
            <span style={s(38, '#ff8c2a')}>{gold}</span>
          </div>
          <div style={{ fontSize: 9, color: 'rgba(255,140,42,0.7)', fontFamily: "'Space Grotesk',sans-serif",
            fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', marginTop: 2 }}>
            💰 Monedas
          </div>
        </div>

        {div}

        {/* Distancia real */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 110 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
            <span style={s(38, '#06b6d4')}>{distKm}</span>
            <span style={s(11, '#06b6d4', { fontWeight: 700 })}>km</span>
          </div>
          <div style={{ fontSize: 9, color: 'rgba(0,240,255,0.7)', fontFamily: "'Space Grotesk',sans-serif",
            fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', marginTop: 2 }}>
            ↗ Recorrido
          </div>
        </div>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────
// Runner Silhouettes — animated neon parade
// ─────────────────────────────────────────────────────────────
const RunnerFigure = ({ gender, color, stride }) => {
  const isFemale = gender === 'female'
  const glow = `drop-shadow(0 0 7px ${color}) drop-shadow(0 0 22px ${color}99)`

  return (
    <svg viewBox="0 0 76 120" fill="none" style={{ overflow: 'visible', filter: glow }}>

      {/* BACK ARM (right, starts BACK) */}
      <g transform="translate(28,25)">
        <g style={{ transformOrigin:'0px 0px', animation:`up-arm-r ${stride}s ease-in-out alternate infinite` }}>
          <line x1="0" y1="0" x2="0" y2="23" stroke={color} strokeWidth="5" strokeLinecap="round" strokeOpacity="0.55"/>
          <line x1="0" y1="23" x2="-11" y2="9" stroke={color} strokeWidth="4" strokeLinecap="round" strokeOpacity="0.55"/>
          <circle cx="-11" cy="6" r="3.5" fill={color} fillOpacity="0.55"/>
        </g>
      </g>

      {/* BACK LEG (left, starts BACK/stance) */}
      <g transform="translate(33,53)">
        <g style={{ transformOrigin:'0px 0px', animation:`up-thigh-l ${stride}s ease-in-out alternate infinite` }}>
          <line x1="0" y1="0" x2="0" y2="28" stroke={color} strokeWidth="11" strokeLinecap="round" strokeOpacity="0.55"/>
          <g style={{ transformOrigin:'0px 28px', animation:`up-shin-l ${stride}s ease-in-out alternate infinite` }}>
            <line x1="0" y1="28" x2="0" y2="52" stroke={color} strokeWidth="8.5" strokeLinecap="round" strokeOpacity="0.55"/>
            <path d="M2 52 Q-4 49 -14 51 Q-17 54 -14 58 Q-4 59 4 56 Q6 54 2 52Z" fill={color} fillOpacity="0.55"/>
          </g>
        </g>
      </g>

      {/* HEAD — perfil mirando a la IZQUIERDA (cuerpo base va a la izquierda, LTR se espeja) */}
      <ellipse cx="37" cy="10" rx="8" ry="10" fill={color}/>
      {/* Nariz apuntando a la izquierda */}
      <path d="M31 8 Q21 11 26 17 Q29 18 32 15 Q33 12 31 8Z" fill={color}/>
      {/* Ojo en el perfil izquierdo */}
      <circle cx="30" cy="8" r="2" fill="#06070d" fillOpacity="0.7"/>

      {/* PONYTAIL (female) — sale por la DERECHA (nuca para figura mirando izquierda) */}
      {isFemale && <path d="M45 4 Q59 0 56 16 Q54 22 47 14" fill={color}/>}

      {/* NECK */}
      <rect x="36" y="19" width="7" height="9" rx="3.5" fill={color}/>

      {/* TORSO */}
      <path d="M24 23 Q35 18 47 23 L44 53 Q35 57 26 53Z" fill={color}/>

      {/* FRONT LEG (right, starts FORWARD/swing) */}
      <g transform="translate(36,53)">
        <g style={{ transformOrigin:'0px 0px', animation:`up-thigh-r ${stride}s ease-in-out alternate infinite` }}>
          <line x1="0" y1="0" x2="0" y2="28" stroke={color} strokeWidth="11" strokeLinecap="round"/>
          <g style={{ transformOrigin:'0px 28px', animation:`up-shin-r ${stride}s ease-in-out alternate infinite` }}>
            <line x1="0" y1="28" x2="0" y2="52" stroke={color} strokeWidth="8.5" strokeLinecap="round"/>
            <path d="M2 52 Q-4 49 -14 51 Q-17 54 -14 58 Q-4 59 4 56 Q6 54 2 52Z" fill={color}/>
          </g>
        </g>
      </g>

      {/* FRONT ARM (left, starts FORWARD) */}
      <g transform="translate(42,25)">
        <g style={{ transformOrigin:'0px 0px', animation:`up-arm-l ${stride}s ease-in-out alternate infinite` }}>
          <line x1="0" y1="0" x2="0" y2="23" stroke={color} strokeWidth="7" strokeLinecap="round"/>
          <line x1="0" y1="23" x2="-11" y2="9" stroke={color} strokeWidth="5.5" strokeLinecap="round"/>
          <circle cx="-11" cy="6" r="4" fill={color}/>
        </g>
      </g>

    </svg>
  )
}
const RunnerFigureMemo = React.memo(RunnerFigure)

/*
 * Runners rediseñados (v2) — paleta Nike negro/blanco + menos ruido.
 *
 * Cambios respecto a v1:
 *   - Reducidos de 10 a 6 para que no saturen el fondo.
 *   - Colores: sólo blanco + un acento (magenta o lima) en 2 de ellos,
 *     el resto blanco puro. Antes era una explosión de 4 colores neón.
 *   - Opacidad máxima 0.28 (antes 0.90) — ambientales, no protagonistas.
 *   - Stride ligeramente más lento para un ritmo de trote profesional.
 *   - topPct distribuye mejor verticalmente (0.15, 0.35, 0.50, 0.65,
 *     0.78, 0.90) sin huecos extraños.
 */
const RUNNERS = [
  // Paleta unificada: solo blanco + Volt. El negro ya es el fondo,
  // así que los runners son blancos (neutro pro) o Volt (acento
  // Nike Running). Mantengo todos los demás parámetros idénticos
  // (scale, top, crossDur, delay, dir, opacity, stride) para no
  // alterar el movimiento.
  { id: 1, gender: 'male',   color: '#ffffff', scale: 1.20, top: '10%', crossDur: 14, delay: 0,  dir: 'ltr', opacity: 0.85, stride: 0.38 },
  { id: 2, gender: 'female', color: '#ffffff', scale: 0.65, top: '55%', crossDur: 22, delay: 4,  dir: 'ltr', opacity: 0.45, stride: 0.50 },
  { id: 3, gender: 'male',   color: '#c8ff00', scale: 0.45, top: '32%', crossDur: 28, delay: 9,  dir: 'ltr', opacity: 0.28, stride: 0.55 },
  { id: 4, gender: 'female', color: '#ffffff', scale: 1.00, top: '68%', crossDur: 17, delay: 12, dir: 'rtl', opacity: 0.70, stride: 0.42 },
  { id: 5, gender: 'male',   color: '#ffffff', scale: 1.35, top: '20%', crossDur: 12, delay: 6,  dir: 'ltr', opacity: 0.90, stride: 0.35 },
  { id: 6, gender: 'female', color: '#c8ff00', scale: 0.75, top: '42%', crossDur: 19, delay: 16, dir: 'ltr', opacity: 0.50, stride: 0.47 },
  { id: 7, gender: 'male',   color: '#ffffff', scale: 1.05, top: '76%', crossDur: 24, delay: 3,  dir: 'rtl', opacity: 0.60, stride: 0.43 },
  { id: 8, gender: 'female', color: '#ffffff', scale: 0.55, top: '62%', crossDur: 30, delay: 21, dir: 'ltr', opacity: 0.32, stride: 0.52 },
  { id: 9, gender: 'male',   color: '#c8ff00', scale: 0.80, top: '85%', crossDur: 16, delay: 8,  dir: 'ltr', opacity: 0.55, stride: 0.46 },
  { id:10, gender: 'female', color: '#ffffff', scale: 1.15, top: '5%',  crossDur: 20, delay: 18, dir: 'rtl', opacity: 0.75, stride: 0.40 },
]

function RunnerParade() {
  // #10 — Reducir carga en dispositivos con prefers-reduced-motion o baja GPU
  const reduceMotion =
    typeof window !== 'undefined' &&
    window.matchMedia &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  const runners = reduceMotion ? RUNNERS.slice(0, 3) : RUNNERS
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none" style={{ zIndex: 1 }}>
      {runners.map(({ id, gender, color, scale, top, crossDur, delay, dir, opacity, stride }) => (
        <div
          key={id}
          style={{
            position: 'absolute',
            top,
            left: 0,
            opacity,
            animation: `${dir === 'ltr' ? 'up-runner-cross-ltr' : 'up-runner-cross-rtl'} ${crossDur}s linear ${delay}s infinite`,
            animationFillMode: 'both',
          }}
        >
          <div style={{ animation: `up-runner-bob ${stride}s ease-in-out alternate infinite` }}>
            <div style={{
              transform: `scale(${scale}) scaleX(${dir === 'ltr' ? -1 : 1})`,
              transformOrigin: 'top left',
              width: 76,
              height: 120,
            }}>
              <RunnerFigureMemo gender={gender} color={color} stride={stride} />
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────
// SVG Sneaker
// ─────────────────────────────────────────────────────────────
function NeonSneaker() {
  return (
    <svg viewBox="0 0 220 140" className="w-full h-auto drop-shadow-[0_15px_35px_rgba(255,45,146,0.5)]">
      <defs>
        <linearGradient id="up-sneaker-body" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#f43f5e" />
          <stop offset="50%" stopColor="#a855f7" />
          <stop offset="100%" stopColor="#06b6d4" />
        </linearGradient>
        <linearGradient id="up-sneaker-sole" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="#ffffff" />
          <stop offset="100%" stopColor="#facc15" />
        </linearGradient>
      </defs>
      <path d="M 20 105 Q 15 120, 30 122 L 200 122 Q 215 120, 210 105 L 200 100 L 25 100 Z"
        fill="url(#up-sneaker-sole)" stroke="#fff" strokeWidth="1.5" />
      {[35, 60, 85, 110, 135, 160, 185].map((x) => (
        <line key={x} x1={x} y1="112" x2={x} y2="120" stroke="#06070d" strokeWidth="2" />
      ))}
      <path d="M 25 100 Q 30 60, 60 50 Q 90 40, 130 45 Q 170 50, 195 70 Q 205 85, 200 100 Z"
        fill="url(#up-sneaker-body)" stroke="#fff" strokeWidth="2" />
      <path d="M 195 70 Q 205 85, 200 100 L 175 100 Q 178 80, 195 70 Z" fill="#fff" opacity="0.25" />
      {[80, 100, 120, 140].map((x) => (
        <g key={x}>
          <line x1={x} y1="55" x2={x + 15} y2="65" stroke="#fff" strokeWidth="2.5" />
          <line x1={x + 15} y1="55" x2={x} y2="65" stroke="#fff" strokeWidth="2.5" />
          <circle cx={x} cy="55" r="1.5" fill="#facc15" />
          <circle cx={x + 15} cy="55" r="1.5" fill="#facc15" />
        </g>
      ))}
      <path d="M 50 80 Q 80 75, 110 78 L 105 92 Q 75 95, 48 92 Z" fill="#fff" stroke="#06070d" strokeWidth="1" />
      <circle cx="160" cy="80" r="10" fill="#06070d" stroke="#facc15" strokeWidth="1.5" />
      <text x="160" y="84" textAnchor="middle" fontSize="10" fontWeight="900" fill="#facc15">UP</text>
    </svg>
  )
}

// ─────────────────────────────────────────────────────────────
// Reward Reel — 10 imágenes running/sport que rotan + dado SVG fallback
// ─────────────────────────────────────────────────────────────
/**
 * 10 fotos temáticas (running, zapatillas, trail, carrera) de Unsplash
 * con licencia libre. Rotan cada 6 segundos dentro del botón de
 * recompensa diaria. Si CUALQUIERA falla al cargar, el fallback es un
 * D6 isométrico SVG dibujado a mano — siempre hay algo que mostrar.
 *
 * Las 7 primeras URLs ya las uso en NeonShoeHero / NeonGrid así que están
 * verificadas. Las 3 últimas son candidatos adicionales — si fallan,
 * el fallback entra sin problema.
 */
const REWARD_IMAGES = [
  // Zapatillas (product shots)
  'https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=400&q=80&auto=format&fit=crop',
  'https://images.unsplash.com/photo-1460353581641-37baddab0fa2?w=400&q=80&auto=format&fit=crop',
  'https://images.unsplash.com/photo-1600185365926-3a2ce3cdb9eb?w=400&q=80&auto=format&fit=crop',
  // Runners en acción
  'https://images.unsplash.com/photo-1461896836934-ffe607ba8211?w=400&q=80&auto=format&fit=crop',
  'https://images.unsplash.com/photo-1571008887538-b36bb32f4571?w=400&q=80&auto=format&fit=crop',
  'https://images.unsplash.com/photo-1552674605-db6ffd4facb5?w=400&q=80&auto=format&fit=crop',
  'https://images.unsplash.com/photo-1486218119243-13883505764c?w=400&q=80&auto=format&fit=crop',
  // Más running / deporte (fallback al SVG si fallan)
  'https://images.unsplash.com/photo-1434682881908-b43d0467b798?w=400&q=80&auto=format&fit=crop',
  'https://images.unsplash.com/photo-1476480862126-209bfaa8edc8?w=400&q=80&auto=format&fit=crop',
  'https://images.unsplash.com/photo-1508215885820-4585e56135c8?w=400&q=80&auto=format&fit=crop',
]

/**
 * Dado D6 SVG isométrico — fallback garantizado.
 */
function DiceSvg() {
  return (
    <svg viewBox="0 0 240 240" style={{ overflow: 'visible', width: '100%', height: '100%' }}>
      <defs>
        <linearGradient id="dice-front" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%"  stopColor="#f5f5f5" />
          <stop offset="100%" stopColor="#c8c8c8" />
        </linearGradient>
        <linearGradient id="dice-top" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%"  stopColor="#ffffff" />
          <stop offset="100%" stopColor="#e8e8e8" />
        </linearGradient>
        <linearGradient id="dice-side" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%"  stopColor="#d5d5d5" />
          <stop offset="100%" stopColor="#8a8a8a" />
        </linearGradient>
      </defs>
      <g transform="translate(50, 28)">
        <polygon points="70,0 140,35 70,70 0,35" fill="url(#dice-top)" stroke="#9e9e9e" strokeWidth="1" strokeLinejoin="round" />
        <ellipse cx="70" cy="35" rx="5"   ry="3"   fill="#1a1a1a" />
        <ellipse cx="42" cy="21" rx="4.5" ry="2.8" fill="#1a1a1a" />
        <ellipse cx="98" cy="21" rx="4.5" ry="2.8" fill="#1a1a1a" />
        <ellipse cx="42" cy="49" rx="4.5" ry="2.8" fill="#1a1a1a" />
        <ellipse cx="98" cy="49" rx="4.5" ry="2.8" fill="#1a1a1a" />
        <polygon points="0,35 70,70 70,170 0,135" fill="url(#dice-front)" stroke="#a0a0a0" strokeWidth="1" strokeLinejoin="round" />
        <ellipse cx="15" cy="58"  rx="5.5" ry="4" fill="#1a1a1a" transform="rotate(-18 15 58)" />
        <ellipse cx="35" cy="100" rx="5.5" ry="4" fill="#1a1a1a" transform="rotate(-18 35 100)" />
        <ellipse cx="55" cy="142" rx="5.5" ry="4" fill="#1a1a1a" transform="rotate(-18 55 142)" />
        <polygon points="70,70 140,35 140,135 70,170" fill="url(#dice-side)" stroke="#6e6e6e" strokeWidth="1" strokeLinejoin="round" />
        <ellipse cx="95"  cy="78"  rx="5" ry="3.5" fill="#1a1a1a" transform="rotate(18 95 78)" />
        <ellipse cx="118" cy="135" rx="5" ry="3.5" fill="#1a1a1a" transform="rotate(18 118 135)" />
      </g>
    </svg>
  )
}

/**
 * Botón de reclamar recompensa diaria — reel de 10 imágenes rotando.
 * Rotan cada 6s con cross-fade. Si una imagen falla, se marca como
 * rota y se usa el DiceSvg como fallback.
 */
function Shoebox({ onClick, claimed, claiming }) {
  const [idx, setIdx] = useState(() => Math.floor(Math.random() * REWARD_IMAGES.length))
  const [failedIdx, setFailedIdx] = useState(new Set())

  useEffect(() => {
    if (claimed || claiming) return
    const timer = setInterval(() => {
      setIdx(i => (i + 1) % REWARD_IMAGES.length)
    }, 6000)
    return () => clearInterval(timer)
  }, [claimed, claiming])

  const currentSrc = REWARD_IMAGES[idx]
  const isBroken = failedIdx.has(idx)

  return (
    <motion.button
      onClick={onClick}
      whileHover={{ scale: (claimed || claiming) ? 1 : 1.06, rotateY: (claimed || claiming) ? 0 : 8 }}
      whileTap={{ scale: (claimed || claiming) ? 1 : 0.95 }}
      animate={claimed ? { opacity: 0.4 } : claiming ? { opacity: [0.7, 1, 0.7] } : { y: [0, -8, 0] }}
      transition={claimed ? {} : claiming ? { duration: 0.8, repeat: Infinity, ease: 'easeInOut' } : { duration: 3, repeat: Infinity, ease: 'easeInOut' }}
      className="relative w-[180px] h-[180px] cursor-pointer rounded-2xl overflow-hidden border border-white/10"
      style={{
        background: '#0a0a0a',
        filter: claimed
          ? 'grayscale(1) brightness(0.7)'
          : claiming
            ? 'drop-shadow(0 0 12px rgba(200,255,0,0.45))'
            : 'drop-shadow(0 10px 24px rgba(0,0,0,0.55)) drop-shadow(0 0 20px rgba(200,255,0,0.18))',
      }}
      disabled={claimed || claiming}
      aria-label="Reclamar recompensa diaria"
    >
      <AnimatePresence mode="wait">
        <motion.div
          key={`${idx}-${isBroken}`}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.6 }}
          className="absolute inset-0"
        >
          {isBroken ? (
            <div className="w-full h-full flex items-center justify-center bg-[#0a0a0a]">
              <DiceSvg />
            </div>
          ) : (
            <img
              src={currentSrc}
              alt="Recompensa"
              onError={() => setFailedIdx(prev => new Set([...prev, idx]))}
              className="w-full h-full object-cover"
              loading="lazy"
            />
          )}
        </motion.div>
      </AnimatePresence>
      {/* Overlay Volt sutil + contador 'N/10' esquina inferior */}
      <div className="absolute inset-0 pointer-events-none"
           style={{ boxShadow: 'inset 0 0 60px rgba(200,255,0,0.12)' }} />
      <div
        className="absolute bottom-1.5 right-2 text-[9px] font-bold uppercase tracking-widest"
        style={{ color: '#c8ff00', textShadow: '0 0 6px rgba(0,0,0,0.9)' }}
      >
        {idx + 1}/{REWARD_IMAGES.length}
      </div>
    </motion.button>
  )
}


// ─────────────────────────────────────────────────────────────
// Tutorial (7 steps — includes Fortify explanation)
// ─────────────────────────────────────────────────────────────
const TUTORIAL_STEPS = [
  {
    icon: Footprints,
    color: '#f43f5e',
    gradient: 'from-[#f43f5e]/30 to-[#a855f7]/20',
    border: '#f43f5e',
    tag: 'Bienvenida',
    title: 'Bienvenido al Asfalto',
    body: 'CloudRISK convierte tus carreras reales en conquista urbana. Cada kilómetro que recorres se traduce en poder para dominar los distritos de Valencia.',
    visual: null,
  },
  {
    icon: MapIcon,
    color: '#06b6d4',
    gradient: 'from-[#06b6d4]/30 to-[#a855f7]/20',
    border: '#06b6d4',
    tag: 'El Mapa',
    title: 'Tu Ciudad, Tu Campo de Batalla',
    body: 'Los 49 distritos de Valencia son tu territorio. El color lo dice todo:',
    visual: 'legend',
  },
  {
    icon: Bolt,
    color: '#facc15',
    gradient: 'from-[#facc15]/25 to-[#06b6d4]/15',
    border: '#facc15',
    tag: 'Energía',
    title: 'Pasos = Poder',
    body: 'Cada 100 pasos reales generan 1 tropa. Cuantas más tropas acumules, más zonas podrás controlar. ¡Sal a correr y crece tu ejército!',
    visual: 'steps',
  },
  {
    icon: Send,
    color: '#facc15',
    gradient: 'from-[#facc15]/25 to-[#f43f5e]/15',
    border: '#facc15',
    tag: 'Desplegar',
    title: 'Despliega Tropas',
    body: 'Toca cualquier zona del mapa y pulsa Desplegar para enviar tropas. Cuantas más tropas tenga un territorio, más difícil será conquistarlo.',
    visual: 'deploy',
  },
  {
    icon: Swords,
    color: '#f43f5e',
    gradient: 'from-[#f43f5e]/30 to-[#a855f7]/20',
    border: '#f43f5e',
    tag: 'Atacar',
    title: 'Batallas con Dados',
    body: 'Ataca territorios rivales y los dados al estilo Risk deciden el ganador. Más tropas = más dados = más probabilidades de victoria.',
    visual: 'dice',
  },
  {
    icon: Shield,
    color: '#06b6d4',
    gradient: 'from-[#06b6d4]/30 to-[#a855f7]/20',
    border: '#06b6d4',
    tag: 'Fortificar',
    title: 'Mueve Tropas entre Territorios',
    body: 'Fortificar te permite redistribuir tus ejércitos estratégicamente. Selecciona un territorio tuyo, elige cuántas tropas mover y a qué zona enviarlas. Refuerza los frentes más débiles sin gastar energía extra.',
    visual: 'fortify',
  },
]

// Sub-visual para cada slide del tutorial
function TutorialVisual({ type }) {
  if (type === 'legend') return (
    <div className="flex justify-center gap-3 mt-4">
      {[['#f43f5e', 'Tuyo'], ['#06b6d4', 'Rival'], ['#facc15', 'Libre']].map(([color, label]) => (
        <div key={label} className="flex flex-col items-center gap-1.5">
          <div className="w-8 h-8 rounded-xl border-2 flex items-center justify-center"
            style={{ borderColor: color, background: `${color}22`, boxShadow: `0 0 12px ${color}66` }}>
            <div className="w-3 h-3 rounded-full" style={{ background: color, boxShadow: `0 0 8px ${color}` }} />
          </div>
          <span className="text-[10px] font-bold uppercase tracking-widest" style={{ color }}>{label}</span>
        </div>
      ))}
    </div>
  )

  if (type === 'steps') return (
    <div className="mt-4 rounded-2xl border border-[#facc15]/30 bg-[#facc15]/08 p-3 flex items-center gap-3">
      <Footprints className="w-6 h-6 text-[#facc15] flex-shrink-0" />
      <div className="flex-1">
        <div className="flex justify-between text-[10px] font-bold mb-1">
          <span className="text-white/50 uppercase tracking-widest">1.000 pasos</span>
          <span style={{ color: '#facc15' }}>10 tropas</span>
        </div>
        <div className="h-2 rounded-full bg-white/10 overflow-hidden">
          <motion.div className="h-full rounded-full" style={{ background: '#facc15', boxShadow: '0 0 8px #facc15' }}
            initial={{ width: '0%' }} animate={{ width: '100%' }} transition={{ duration: 1.5, ease: 'easeOut' }} />
        </div>
      </div>
    </div>
  )

  if (type === 'deploy') return (
    <div className="mt-4 flex items-center justify-center gap-2">
      {[{ label: 'El Carmen', armies: 3, color: '#facc15' }, { label: '→', armies: null, color: 'transparent' }, { label: 'Benimaclet', armies: 7, color: '#facc15' }].map((z, i) =>
        z.armies === null
          ? <Send key={i} className="w-5 h-5 text-white/40" />
          : (
            <div key={i} className="flex flex-col items-center gap-1 px-3 py-2 rounded-xl border"
              style={{ borderColor: `${z.color}44`, background: `${z.color}11` }}>
              <span className="text-[10px] text-white/50 font-bold uppercase tracking-wide">{z.label}</span>
              <span className="font-display font-extrabold text-lg" style={{ color: z.color }}>{z.armies}</span>
              <span className="text-[9px] text-white/30">tropas</span>
            </div>
          )
      )}
    </div>
  )

  if (type === 'dice') return (
    <div className="mt-4 flex justify-center gap-2">
      {[['#f43f5e', [6, 4]], ['#06b6d4', [3, 1]]].map(([color, vals], gi) => (
        <div key={gi} className="flex flex-col items-center gap-1">
          <span className="text-[9px] font-bold uppercase tracking-widest" style={{ color }}>{gi === 0 ? 'Atacante' : 'Defensor'}</span>
          <div className="flex gap-1">
            {vals.map((v, i) => (
              <div key={i} className="w-8 h-8 rounded-lg border-2 grid place-items-center font-display font-extrabold text-sm"
                style={{ borderColor: color, background: `${color}22`, color }}>
                {v}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )

  if (type === 'fortify') return (
    <div className="mt-4 rounded-2xl border border-[#06b6d4]/30 bg-[#06b6d4]/05 p-3">
      <div className="flex items-center gap-2 mb-2">
        <div className="flex-1 flex items-center gap-2 px-2 py-1.5 rounded-lg border border-[#06b6d4]/30 bg-[#06b6d4]/10">
          <Shield className="w-3.5 h-3.5 text-[#06b6d4]" />
          <div>
            <div className="text-[9px] text-white/40 uppercase tracking-wide font-bold">Origen</div>
            <div className="text-xs font-bold text-white">El Carmen · 8 tropas</div>
          </div>
        </div>
        <motion.div animate={{ x: [0, 4, 0] }} transition={{ duration: 0.9, repeat: Infinity }}>
          <ChevronRight className="w-4 h-4 text-[#06b6d4]" />
        </motion.div>
        <div className="flex-1 flex items-center gap-2 px-2 py-1.5 rounded-lg border border-[#06b6d4]/50 bg-[#06b6d4]/15">
          <Shield className="w-3.5 h-3.5 text-[#06b6d4]" />
          <div>
            <div className="text-[9px] text-white/40 uppercase tracking-wide font-bold">Destino</div>
            <div className="text-xs font-bold text-white">Ruzafa · 2 tropas</div>
          </div>
        </div>
      </div>
      <div className="text-center text-[10px] text-[#06b6d4]/70 font-bold">
        Mover 5 tropas → Ruzafa queda con 7
      </div>
    </div>
  )

  return null
}

function Tutorial({ onClose }) {
  const [step, setStep] = useState(0)
  const current = TUTORIAL_STEPS[step]
  const Icon = current.icon
  const isLast = step === TUTORIAL_STEPS.length - 1
  const total = TUTORIAL_STEPS.length

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(2,3,10,0.85)', backdropFilter: 'blur(8px)' }}
    >
      <motion.div
        initial={{ scale: 0.88, y: 28, opacity: 0 }}
        animate={{ scale: 1, y: 0, opacity: 1 }}
        transition={{ type: 'spring', damping: 22, stiffness: 260 }}
        className="relative w-full max-w-md rounded-3xl overflow-hidden border"
        style={{
          borderColor: `${current.border}44`,
          background: 'linear-gradient(180deg, rgba(14,14,32,0.98), rgba(6,7,16,0.98))',
          boxShadow: `0 24px 80px ${current.color}33, 0 0 0 1px ${current.color}22`,
        }}
      >
        {/* Glow top accent */}
        <div className="absolute top-0 left-0 right-0 h-px"
          style={{ background: `linear-gradient(90deg, transparent, ${current.color}, transparent)` }} />
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-40 h-20 rounded-full blur-3xl pointer-events-none"
          style={{ background: `${current.color}22` }} />

        <div className="relative p-7">

          {/* Header — tag + step counter */}
          <div className="flex items-center justify-between mb-5">
            <div className="flex items-center gap-2 px-3 py-1 rounded-full border"
              style={{ borderColor: `${current.color}50`, background: `${current.color}15` }}>
              <BookOpen className="w-3 h-3" style={{ color: current.color }} />
              <span className="text-[10px] uppercase tracking-widest font-bold" style={{ color: current.color }}>
                {current.tag}
              </span>
            </div>
            <span className="text-[11px] font-bold text-white/30 font-mono">{step + 1} / {total}</span>
          </div>

          {/* Progress bar */}
          <div className="flex gap-1.5 mb-6">
            {TUTORIAL_STEPS.map((_, i) => (
              <motion.div
                key={i}
                className="h-1 rounded-full flex-1 cursor-pointer"
                style={{ background: i < step ? current.color : i === step ? current.color : 'rgba(255,255,255,0.12)' }}
                animate={{ opacity: i === step ? 1 : i < step ? 0.6 : 0.3 }}
                onClick={() => setStep(i)}
              />
            ))}
          </div>

          {/* Slide content */}
          <AnimatePresence mode="wait">
            <motion.div
              key={step}
              initial={{ opacity: 0, x: 24 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -24 }}
              transition={{ duration: 0.22 }}
            >
              {/* Icon */}
              <div className="flex justify-center mb-5">
                <div className={`relative p-5 rounded-3xl bg-gradient-to-br ${current.gradient} border`}
                  style={{ borderColor: `${current.color}44`, boxShadow: `0 0 40px ${current.color}33` }}>
                  <Icon className="w-10 h-10" style={{ color: current.color }} />
                  {/* Corner glow */}
                  <div className="absolute -top-1 -right-1 w-3 h-3 rounded-full"
                    style={{ background: current.color, boxShadow: `0 0 10px ${current.color}` }} />
                </div>
              </div>

              <h3 className="font-display text-xl font-extrabold text-white text-center mb-2 leading-tight">
                {current.title}
              </h3>
              <p className="text-white/65 leading-relaxed text-sm text-center">
                {current.body}
              </p>

              {/* Visual extra por slide */}
              <TutorialVisual type={current.visual} />
            </motion.div>
          </AnimatePresence>

          {/* Navigation */}
          <div className="flex gap-3 mt-7">
            {step > 0 ? (
              <motion.button
                whileTap={{ scale: 0.96 }}
                onClick={() => setStep(s => s - 1)}
                className="flex items-center justify-center gap-1 px-4 py-3 rounded-xl border border-white/10 text-white/50 hover:text-white hover:border-white/25 transition font-display font-bold text-sm"
              >
                <ChevronLeft className="w-4 h-4" /> Atrás
              </motion.button>
            ) : (
              <motion.button
                whileTap={{ scale: 0.96 }}
                onClick={onClose}
                title="El tutorial no volverá a aparecer automáticamente"
                className="px-4 py-3 rounded-xl border border-white/10 text-white/40 hover:text-white/70 transition font-display font-bold text-sm flex flex-col items-center leading-tight"
              >
                <span>Saltar</span>
                <span className="text-[9px] font-normal text-white/25 normal-case tracking-normal">no volver a mostrar</span>
              </motion.button>
            )}
            <motion.button
              whileHover={{ scale: 1.03 }}
              whileTap={{ scale: 0.97 }}
              onClick={() => isLast ? onClose() : setStep(s => s + 1)}
              className="flex-1 flex items-center justify-center gap-2 py-3 rounded-xl font-display font-extrabold text-sm text-white"
              style={{
                background: `linear-gradient(135deg, ${current.color}, #a855f7)`,
                boxShadow: `0 6px 24px ${current.color}55`,
                color: current.color === '#facc15' ? '#06070d' : '#fff',
              }}
            >
              {isLast ? (
                <><Zap className="w-4 h-4" /> ¡A Conquistar!</>
              ) : (
                <>Siguiente <ChevronRight className="w-4 h-4" /></>
              )}
            </motion.button>
          </div>
        </div>
      </motion.div>
    </motion.div>
  )
}

// ─────────────────────────────────────────────────────────────
// LOGIN VIEW (with real backend register/login)
// ─────────────────────────────────────────────────────────────
function LoginView({ wsStatus = 'idle', player = null }) {
  const { login } = useAuth()
  const [mode, setMode] = useState('login')
  const [form, setForm] = useState({ name: '', email: '', password: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      let res
      if (mode === 'login') {
        const params = new URLSearchParams()
        params.append('username', form.email)
        params.append('password', form.password)
        res = await api.post('/api/v1/users/login', params, {
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        })
      } else {
        res = await api.post('/api/v1/users/register', {
          name: form.name,
          email: form.email,
          password: form.password,
        })
      }
      login(res.data.access_token, res.data.user)
    } catch (err) {
      setError(err.response?.data?.detail || 'Error de autenticacion')
    } finally {
      setLoading(false)
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="absolute inset-0 flex items-center justify-center px-6"
    >
      <NeonGrid />
      <RunnerParade />
      <PlayerStatsBar player={player} />
      <div className="absolute top-4 right-4 z-20">
        <WsIndicator status={wsStatus} />
      </div>
      <motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ delay: 0.1, type: 'spring' }}
        className="relative z-10 w-full max-w-md"
      >
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-3 mb-3">
            <div className="p-3 rounded-2xl bg-gradient-to-br from-neon-pink to-neon-violet shadow-glow">
              <Footprints className="w-8 h-8 text-white" strokeWidth={2.5} />
            </div>
            <h1 className="font-display text-5xl font-extrabold tracking-tight bg-gradient-to-r from-neon-pink via-neon-violet to-neon-cyan bg-clip-text text-transparent">
              CloudRISK
            </h1>
          </div>
          <p className="text-white/60 text-sm font-medium tracking-widest uppercase">Run · Conquer · Repeat</p>
        </div>

        <div className="rounded-3xl p-8 bg-white/5 backdrop-blur-xl border border-white/10 shadow-2xl">
          <h2 className="font-display text-2xl font-bold text-white mb-1">
            {mode === 'login' ? 'Sincroniza tus zapatillas' : 'Crea tu perfil de runner'}
          </h2>
          <p className="text-white/50 text-sm mb-5">Conecta tu cuenta y empieza a conquistar</p>

          <div className="flex gap-2 mb-5">
            <button
              type="button"
              onClick={() => setMode('login')}
              className={`flex-1 py-2 rounded-xl text-sm font-display font-bold transition ${
                mode === 'login'
                  ? 'bg-neon-pink/20 border-2 border-neon-pink text-neon-pink shadow-[0_0_12px_rgba(255,45,146,0.4)]'
                  : 'bg-transparent border border-neon-pink/40 text-neon-pink hover:border-neon-pink hover:bg-neon-pink/10'
              }`}
            >
              Entrar
            </button>
            <button
              type="button"
              onClick={() => setMode('register')}
              className={`flex-1 py-2 rounded-xl text-sm font-display font-bold transition ${
                mode === 'register'
                  ? 'bg-neon-cyan/20 border-2 border-neon-cyan text-neon-cyan shadow-[0_0_12px_rgba(0,240,255,0.4)]'
                  : 'bg-transparent border border-neon-cyan/40 text-neon-cyan hover:border-neon-cyan hover:bg-neon-cyan/10'
              }`}
            >
              Crear
            </button>
          </div>

          <form onSubmit={handleSubmit}>
            {mode === 'register' && (
              <input
                type="text"
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                placeholder="Nombre de runner"
                required
                className="w-full px-4 py-3 rounded-xl bg-ink-700 border border-white/10 text-white placeholder-white/40 mb-3 focus:outline-none focus:border-neon-pink transition"
              />
            )}
            <input
              type="email"
              value={form.email}
              onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
              placeholder="tu.email@runner.io"
              required
              className="w-full px-4 py-3 rounded-xl bg-ink-700 border border-white/10 text-white placeholder-white/40 mb-3 focus:outline-none focus:border-neon-pink transition"
            />
            <input
              type="password"
              value={form.password}
              onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
              placeholder="Contraseña"
              required
              className="w-full px-4 py-3 rounded-xl bg-ink-700 border border-white/10 text-white placeholder-white/40 mb-4 focus:outline-none focus:border-neon-pink transition"
            />

            {error && (
              <div className="mb-4 px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm">
                {error}
              </div>
            )}

            <motion.button
              type="submit"
              disabled={loading}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              className="w-full py-4 rounded-2xl font-display font-bold text-lg text-white bg-gradient-to-r from-neon-pink to-neon-violet shadow-glow flex items-center justify-center gap-2 disabled:opacity-50"
            >
              <Zap className="w-5 h-5" />
              {loading ? 'Sincronizando...' : (mode === 'login' ? 'ENTRAR AL ASFALTO' : 'EMPEZAR A CORRER')}
            </motion.button>
          </form>
        </div>
      </motion.div>
    </motion.div>
  )
}

// ─────────────────────────────────────────────────────────────
// MAPLIBRE Map with real Valencia GeoJSON
// ─────────────────────────────────────────────────────────────
const NEON_DARK_STYLE = {
  version: 8,
  // Glyph endpoint required by the zones-labels symbol layer (collision-aware
  // zone names). Uses MapLibre's public demo glyphs — no API key needed.
  glyphs: 'https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf',
  sources: {
    dark: {
      type: 'raster',
      tiles: ['https://tiles.stadiamaps.com/tiles/alidade_smooth_dark/{z}/{x}/{y}.png'],
      tileSize: 256,
      attribution: '© Stadia Maps · © OpenMapTiles · © OSM',
    },
  },
  layers: [{ id: 'dark', type: 'raster', source: 'dark' }],
}

// Robust GeoJSON loader: tolerates 404 HTML, bad content-type, empty features
// B-1: acepta AbortSignal para cancelar el fetch si el componente se desmonta
async function loadValenciaGeoJSON(signal) {
  const paths = ['/valencia_districts.geojson', '/valencia_original_57.geojson']
  for (const p of paths) {
    try {
      const r = await fetch(p, {
        headers: { Accept: 'application/geo+json,application/json' },
        signal,
      })
      if (!r.ok) continue
      const ct = r.headers.get('content-type') || ''
      if (!ct.includes('json') && !ct.includes('geo+json')) continue
      const data = await r.json()
      if (data?.features?.length) return data
    } catch (e) {
      if (e.name === 'AbortError') return null
      // try next path
    }
  }
  return null
}

// Per-player colours so every Comandante paints their zones differently.
// Fuente única: PLAYERS (módulo). Falls back to a deterministic hash colour
// for any unknown owner ID so future players still render.
const FREE_COLOR = '#6b7280'   // neutral grey for unclaimed zones

function colorForOwner(ownerId) {
  if (!ownerId) return FREE_COLOR
  if (PLAYERS[ownerId]) return PLAYERS[ownerId].color
  // Unknown owner (e.g. future 5th player) → deterministic colour from id hash.
  let h = 0
  for (let i = 0; i < ownerId.length; i++) h = (h * 31 + ownerId.charCodeAt(i)) | 0
  const hue = Math.abs(h) % 360
  return `hsl(${hue}, 80%, 55%)`
}

// Apply server data onto geojson features, computing ownership color
function applyServerDataToGeoJSON(geojson, serverData, clanId, userId) {
  const byName = new Map(
    (serverData || []).map(l => [String(l.name || '').toLowerCase(), l])
  )
  const features = geojson.features.map((f, i) => {
    const m = byName.get(String(f.properties.name || '').toLowerCase()) || {}
    const ownerClan = m.owner_clan_id || ''
    const ownerUser = m.dominant_user_id || ''
    // Prefer the zone's explicit owner (what /armies/place writes); fall back
    // to any clan id the zone might carry (legacy path).
    const ownerId = ownerUser || ownerClan
    const isMine =
      (!!clanId && ownerClan === clanId) ||
      (!!userId && ownerId === userId)
    f.properties.color = colorForOwner(ownerId)
    f.properties.totalArmies = m.total_armies || m.defense_level || 0
    f.properties.ownerClanId = ownerClan
    f.properties.ownerUserId = ownerUser
    f.properties.ownerClanName = m.owner_clan_name || ''
    // Only set zoneId if backend actually gave us one — no fake fallback
    f.properties.zoneId = m.id || m.location_id || null
    f.properties.isMine = isMine
    if (f.id === undefined) f.id = i
    return f
  })
  return { ...geojson, features }
}

// ─────────────────────────────────────────────────────────────
// View mode helpers — compute MapLibre paint expressions per mode
// ─────────────────────────────────────────────────────────────
function getViewModePaint(mode, battleZoneIds = new Set()) {
  switch (mode) {
    case 'pressure':
      // Presión: zones under attack glow red, owned=dim amber, free=very dim
      return {
        fillColor: ['case',
          ['in', ['get', 'zoneId'], ['literal', [...battleZoneIds]]], '#f43f5e',
          ['!=', ['get', 'color'], '#facc15'], '#ff8c2a',
          'rgba(255,255,255,0.08)',
        ],
        fillOpacity: ['case',
          ['in', ['get', 'zoneId'], ['literal', [...battleZoneIds]]], 0.55,
          ['!=', ['get', 'color'], '#facc15'], 0.22,
          0.06,
        ],
        lineColor: ['case',
          ['in', ['get', 'zoneId'], ['literal', [...battleZoneIds]]], '#f43f5e',
          '#ffffff22',
        ],
      }
    case 'economy':
      // Economía: color intensity based on strategic_value (1–9)
      // High value = bright lime, low = dim blue
      return {
        fillColor: ['interpolate', ['linear'],
          ['coalesce', ['get', 'strategicValue'], 1],
          1, '#06b6d4',
          5, '#a855f7',
          9, '#facc15',
        ],
        fillOpacity: ['interpolate', ['linear'],
          ['coalesce', ['get', 'strategicValue'], 1],
          1, 0.12,
          9, 0.48,
        ],
        lineColor: ['interpolate', ['linear'],
          ['coalesce', ['get', 'strategicValue'], 1],
          1, '#06b6d488',
          9, '#facc1588',
        ],
      }
    default:
      // Control: default clan color
      return {
        fillColor: ['get', 'color'],
        fillOpacity: ['case', ['boolean', ['feature-state', 'hover'], false], 0.45, 0.18],
        lineColor: ['get', 'color'],
      }
  }
}

const NeonMap = React.memo(NeonMapImpl)
function NeonMapImpl({ onZoneClick, currentClanId, currentUserId, refreshKey = 0, viewMode = 'control', battles = [], actionsRef }) {
  const containerRef = useRef(null)
  const mapRef = useRef(null)
  const markersRef = useRef([])
  const geojsonRef = useRef(null)
  const mapReadyRef = useRef(false)
  const [loadError, setLoadError] = useState(null)
  const [retryTick, setRetryTick] = useState(0)

  // Keep latest identifiers + click handler in refs to avoid re-init
  const clanIdRef = useRef(currentClanId)
  const userIdRef = useRef(currentUserId)
  useEffect(() => { clanIdRef.current = currentClanId }, [currentClanId])
  useEffect(() => { userIdRef.current = currentUserId }, [currentUserId])

  const onClickRef = useRef(onZoneClick)
  useEffect(() => { onClickRef.current = onZoneClick }, [onZoneClick])

  // Both zone names AND troop-count badges are rendered by MapLibre symbol
  // layers (see map.on('load') below) so they get collision detection.
  // No HTML markers are created any more — the dense centre of Valencia stays
  // readable at any zoom because the engine hides labels that would clash.
  const rebuildMarkers = useCallback(() => {
    const map = mapRef.current
    const gj = geojsonRef.current
    if (!map || !gj) return
    const src = map.getSource('zones')
    if (src) src.setData(gj)
    const csrc = map.getSource('zones-centroids')
    if (csrc) {
      csrc.setData({
        type: 'FeatureCollection',
        features: gj.features.map(f => ({
          type: 'Feature',
          properties: f.properties,
          geometry: { type: 'Point', coordinates: getCentroid(f.geometry) },
        })),
      })
    }
  }, [])

  // #3 — INIT ONCE (deps vacías). Reinicio sólo vía retryTick manual.
  useEffect(() => {
    let cancelled = false
    let rafId = null // pulsing glow animation frame
    const abortCtrl = new AbortController() // B-1: cancelar fetch GeoJSON al desmontar
    setLoadError(null)
    mapReadyRef.current = false

    const map = new maplibregl.Map({
      container: containerRef.current,
      // OpenFreeMap dark vector style — free, no API key, includes a
      // "building" source-layer that we extrude in 3D below.
      style: 'https://tiles.openfreemap.org/styles/dark',
      center: [-0.39, 39.465],
      zoom: 13.5,
      pitch: 50,         // tilt camera for the 3D view
      bearing: -10,
      antialias: true,   // smoother building edges
      attributionControl: false,
    })
    mapRef.current = map
    // NavigationControl eliminado. Los botones +/− no respondían al click
    // de forma fiable en el tema oscuro (reportado por usuario) y el zoom
    // con rueda del ratón / pinch en móvil funciona por defecto en
    // MapLibre, así que son redundantes. Dejamos sólo el botón de
    // "Centrar en mis zonas" que sí es específico del juego.

    // Exponemos una acción imperativa al padre: "centerOnMyZones". Calcula
    // el bounding box de mis zonas y hace fitBounds. Si no tengo ninguna,
    // vuelve al centro de Valencia. El padre puede colocar el botón donde
    // mejor le convenga (en MapView lo rendeamos debajo del HUD, no dentro
    // del mapa, para evitar que el HUD lo tape).
    if (actionsRef) {
      actionsRef.current = {
        centerOnMyZones: () => {
          const gj = geojsonRef.current
          if (!gj || !mapRef.current) return
          const mine = gj.features.filter(f => f.properties?.isMine)
          if (mine.length === 0) {
            mapRef.current.flyTo({ center: [-0.39, 39.465], zoom: 13, speed: 1.2 })
            return
          }
          let minLng = Infinity, maxLng = -Infinity, minLat = Infinity, maxLat = -Infinity
          mine.forEach(f => {
            const ring = f.geometry.type === 'Polygon'
              ? f.geometry.coordinates[0]
              : f.geometry.coordinates[0][0]
            ring.forEach(([lng, lat]) => {
              if (lng < minLng) minLng = lng
              if (lng > maxLng) maxLng = lng
              if (lat < minLat) minLat = lat
              if (lat > maxLat) maxLat = lat
            })
          })
          mapRef.current.fitBounds([[minLng, minLat], [maxLng, maxLat]], {
            padding: 60, duration: 900, maxZoom: 14.5,
          })
        },
<<<<<<< Front_Ricardo
=======
        // Vuela a una zona concreta (la que ha conquistado / atacado un bot).
        // Opcional: opts.zoom y opts.duration.
>>>>>>> main
        flyToZone: (zoneId, opts = {}) => {
          const gj = geojsonRef.current
          if (!gj || !mapRef.current) return
          const f = gj.features.find(ft => ft.properties?.zoneId === zoneId)
          if (!f) return
          const [lng, lat] = getCentroid(f.geometry)
          mapRef.current.easeTo({
            center: [lng, lat],
            zoom: opts.zoom ?? 14.2,
            duration: opts.duration ?? 900,
            essential: true,
          })
        },
<<<<<<< Front_Ricardo
=======
        // Pulso breve sobre una zona — marca 'pulse: true' en feature-state.
        // El color del pulso lo lee la capa 'zones-pulse' desde la propia
        // propiedad `color` de la feature (color del owner actual), así NO
        // tenemos que mutar el GeoJSON ni llamar setData — sólo feature-state.
>>>>>>> main
        pulseZone: (zoneId, { duration = 2200 } = {}) => {
          const map = mapRef.current
          const gj = geojsonRef.current
          if (!map || !gj) return
          const f = gj.features.find(ft => ft.properties?.zoneId === zoneId)
          if (!f) return
          try {
            map.setFeatureState({ source: 'zones', id: f.id }, { pulse: true })
            setTimeout(() => {
              try {
                map.setFeatureState({ source: 'zones', id: f.id }, { pulse: false })
              } catch {}
            }, duration)
          } catch {}
        },
      }
    }

    map.on('load', async () => {
      const geojson = await loadValenciaGeoJSON(abortCtrl.signal) // B-1
      if (cancelled || !mapRef.current) return
      if (!geojson) {
        setLoadError('No se pudo cargar el mapa de Valencia')
        return
      }

      // Server data — both endpoints tried, silent if both fail
      let serverData = []
      try {
        const r = await api.get('/api/v1/state/locations')
        serverData = Array.isArray(r.data) ? r.data : []
      } catch {
        try {
          const r = await api.get('/api/v1/zones/')
          serverData = Array.isArray(r.data) ? r.data : []
        } catch {}
      }
      if (cancelled || !mapRef.current) return

      // M-4: applyServerDataToGeoJSON devuelve nuevo objeto (no muta)
      const enriched = applyServerDataToGeoJSON(geojson, serverData, clanIdRef.current, userIdRef.current)
      geojsonRef.current = enriched

      // Point source: one Point at each zone's centroid. Used by badge + label
      // layers so we get exactly ONE marker per zone (a polygon source would
      // render one circle/label per vertex of the polygon — disastrous).
      const centroids = {
        type: 'FeatureCollection',
        features: geojson.features.map(f => ({
          type: 'Feature',
          properties: f.properties,
          geometry: { type: 'Point', coordinates: getCentroid(f.geometry) },
        })),
      }

      map.addSource('zones', { type: 'geojson', data: geojson })
      map.addSource('zones-centroids', { type: 'geojson', data: centroids })

      // 3D building extrusions from the OpenFreeMap "openmaptiles" vector
      // source. Buildings are progressively faded in around zoom 13 so the
      // city overview stays readable; full opacity from zoom 15+.
      // Inserted BELOW our zone fill so polygon glow still tints buildings.
      try {
        map.addLayer({
          id: 'buildings-3d',
          type: 'fill-extrusion',
          source: 'openmaptiles',
          'source-layer': 'building',
          minzoom: 12,
          paint: {
            'fill-extrusion-color': [
              'interpolate', ['linear'], ['get', 'render_height'],
              0, '#1f1f3a',
              50, '#3b3b6e',
              100, '#5e3aa1',
              200, '#8b2e9c',
            ],
            'fill-extrusion-height': [
              'interpolate', ['linear'], ['zoom'],
              12, 0,
              13.5, ['get', 'render_height'],
            ],
            'fill-extrusion-base': ['get', 'render_min_height'],
            'fill-extrusion-opacity': 0.85,
          },
        })
        // Layer order: basemap → buildings-3d → (zone layers added below)
      } catch (e) {
        // Style might not have an 'openmaptiles' source — fail soft.
        console.warn('[CloudRISK] 3D building layer unavailable:', e.message)
      }
      map.addLayer({
        id: 'zones-glow',
        type: 'fill',
        source: 'zones',
        paint: {
          'fill-color': ['get', 'color'],
          // Opacidad en 3 casos:
          //   - hover → 0.50 (destaca al pasar el ratón)
          //   - isMine → 0.32 (mis territorios siempre resaltados con color de facción)
          //   - resto → 0.07 (enemigos y libres tenues para que se vea el mapa 3D debajo)
          'fill-opacity': [
            'case',
            ['boolean', ['feature-state', 'hover'], false], 0.50,
            ['==', ['get', 'isMine'], true], 0.32,
            0.07,
          ],
        },
      })
      map.addLayer({
        id: 'zones-border',
        type: 'line',
        source: 'zones',
        paint: {
          'line-color': ['get', 'color'],
          // Mis zonas con borde más grueso (3px vs 1.5px) para que salten a la vista.
          'line-width': [
            'case',
            ['boolean', ['feature-state', 'hover'], false], 4,
            ['==', ['get', 'isMine'], true], 3,
            1.5,
          ],
          'line-opacity': ['case', ['==', ['get', 'isMine'], true], 1.0, 0.9],
        },
      })
      // Troop-count badge — single symbol layer with the number as text and a
      // wide colored halo as the badge "circle". Combining circle + number in
      // one layer guarantees they appear and disappear TOGETHER (no orphan
      // circles without numbers in dense areas).
      map.addLayer({
        id: 'zones-badges',
        type: 'symbol',
        source: 'zones-centroids',
        layout: {
          'text-field': ['to-string', ['coalesce', ['get', 'totalArmies'], 0]],
          'text-font': ['Noto Sans Bold'],
          'text-size': [
            'interpolate', ['linear'], ['zoom'],
            11, 11,
            13, 13,
            15, 16,
            17, 20,
          ],
          // Badge always shows — it's game-critical info. Numbers in dense
          // areas may overlap each other but they are short (1-3 digits) so
          // it stays readable.
          'text-allow-overlap': true,
          'text-ignore-placement': true,
          'symbol-placement': 'point',
          'text-anchor': 'center',
        },
        paint: {
          'text-color': '#06070d',
          // Halo is the "circle": coloured by zone owner, wide and slightly
          // blurred for a glow effect.
          'text-halo-color': ['get', 'color'],
          'text-halo-width': 5,
          'text-halo-blur': 1.5,
        },
      })
      // Zone names — symbol layer with collision detection: overlapping labels
      // are hidden until you zoom in enough.
      map.addLayer({
        id: 'zones-labels',
        type: 'symbol',
        source: 'zones-centroids',
        layout: {
          'text-field': ['get', 'name'],
          // demotiles.maplibre.org glyph catalog only serves "Noto Sans Bold" and
          // "Noto Sans Regular"; listing unavailable fallbacks causes 404 on the
          // whole fontstack URL (MapLibre requests the stack as one comma list).
          'text-font': ['Noto Sans Bold'],
          // Size grows with zoom; at zoom 12 (default) labels are small so more
          // fit without colliding. Zoom in to see every zone's name.
          'text-size': [
            'interpolate', ['linear'], ['zoom'],
            11, 8,
            13, 10,
            15, 12,
            17, 14,
          ],
          'text-transform': 'uppercase',
          'text-letter-spacing': 0.05,
          'text-max-width': 7,
          // More padding = stricter collision detection = cleaner map at low zoom.
          'text-padding': 6,
          'text-allow-overlap': false,
          'text-ignore-placement': false,
          'symbol-placement': 'point',
          // Place the label BELOW the troop-count badge so they don't overlap.
          'text-anchor': 'top',
          'text-offset': [0, 1.1],
        },
        paint: {
          'text-color': '#ffffff',
          'text-halo-color': '#000000',
          'text-halo-width': 1.8,
          'text-halo-blur': 0.4,
        },
      })

<<<<<<< Front_Ricardo
      // Pulse layer — activada vía feature-state 'pulse' cuando un bot ataca/conquista/fortifica.
=======
      // Pulse layer — activada vía feature-state 'pulse' cuando un bot
      // ataca / conquista / fortifica. Pinta un borde grueso del color del
      // propio polígono (propiedad `color` = owner) durante ~2s.
      // No intercepta clicks (type=line) y evita cualquier setData.
>>>>>>> main
      map.addLayer({
        id: 'zones-pulse',
        type: 'line',
        source: 'zones',
        paint: {
          'line-color': ['get', 'color'],
<<<<<<< Front_Ricardo
          'line-width': ['case', ['boolean', ['feature-state', 'pulse'], false], 8, 0],
          'line-opacity': ['case', ['boolean', ['feature-state', 'pulse'], false], 0.9, 0],
=======
          'line-width': [
            'case',
            ['boolean', ['feature-state', 'pulse'], false], 8,
            0,
          ],
          'line-opacity': [
            'case',
            ['boolean', ['feature-state', 'pulse'], false], 0.9,
            0,
          ],
>>>>>>> main
          'line-blur': 2,
        },
      })

      rebuildMarkers()

      // ── Battlefield layers (inserted before zones-border to preserve order) ──
<<<<<<< Front_Ricardo
      // Fog of War: unclaimed zones get a dark overlay — feel unexplored.
      // Filtramos por FREE_COLOR (gris) en lugar de '#facc15' (que ahora es el Sur).
=======
      // Fog of War: unclaimed zones get a dark overlay → feel unexplored.
      //
      // BUG encontrado en la auditoría: el filtro original era
      // `['==', ['get', 'color'], '#facc15']` porque en la paleta ANTIGUA el
      // amarillo lima era el color de "libre". La paleta actual (FREE_COLOR
      // = '#6b7280' gris) asigna amarillo al jugador Sur, así que la niebla
      // de guerra se estaba pintando encima de las zonas de Sur y dejaba
      // sólo los bordes amarillos visibles (sin fill). Nueva regla: filtrar
      // explícitamente por FREE_COLOR (gris).
>>>>>>> main
      map.addLayer({
        id: 'zones-fog',
        type: 'fill',
        source: 'zones',
        filter: ['==', ['get', 'color'], FREE_COLOR],
        paint: { 'fill-color': '#000205', 'fill-opacity': 0.38 },
      }, 'zones-border')

      // Owned/rival glow: animated breathing fill — territories feel alive.
<<<<<<< Front_Ricardo
      // Excluye FREE_COLOR (gris) en lugar del amarillo que ahora pertenece al Sur.
=======
      // Misma corrección: antes excluía amarillo pensando que era "libre";
      // ahora excluye explícitamente el color de libre (gris).
>>>>>>> main
      map.addLayer({
        id: 'zones-owned-glow',
        type: 'fill',
        source: 'zones',
        filter: ['!=', ['get', 'color'], FREE_COLOR],
        paint: { 'fill-color': ['get', 'color'], 'fill-opacity': 0.28 },
      }, 'zones-fog')

      // RAF pulse: sine wave drives fill-opacity for owned/rival zones
      let glowPhase = 0
      const animateGlow = () => {
        if (!mapRef.current) return
        glowPhase += 0.018
        const opacity = 0.22 + Math.sin(glowPhase) * 0.13
        try { mapRef.current.setPaintProperty('zones-owned-glow', 'fill-opacity', opacity) } catch {}
        rafId = requestAnimationFrame(animateGlow)
      }
      rafId = requestAnimationFrame(animateGlow)

      // Hover
      let hoveredId = null
      map.on('mousemove', 'zones-glow', (e) => {
        if (!e.features?.length) return
        if (hoveredId !== null) map.setFeatureState({ source: 'zones', id: hoveredId }, { hover: false })
        hoveredId = e.features[0].id
        map.setFeatureState({ source: 'zones', id: hoveredId }, { hover: true })
        map.getCanvas().style.cursor = 'pointer'
      })
      map.on('mouseleave', 'zones-glow', () => {
        if (hoveredId !== null) map.setFeatureState({ source: 'zones', id: hoveredId }, { hover: false })
        hoveredId = null
        map.getCanvas().style.cursor = ''
      })

      // #5 — Click: guard zonas sin sync con el backend
      map.on('click', 'zones-glow', (e) => {
        if (!e.features?.length) return
        const p = e.features[0].properties
        onClickRef.current?.({
          id: p.zoneId || null, // null ⇒ ActionPanel mostrará aviso
          name: p.name,
          total_armies: p.totalArmies || 0,
          defense_level: p.totalArmies || 0,
          owner_clan_id: p.ownerClanId || '',
          owner_clan_name: p.ownerClanName || '',
          color: p.color,
          isMine: p.isMine,
          _unsynced: !p.zoneId,
        })
      })

      mapReadyRef.current = true
    })

    return () => {
      cancelled = true
      if (rafId !== null) cancelAnimationFrame(rafId)
      abortCtrl.abort() // B-1: cancela el fetch del GeoJSON si el componente se desmonta
      mapReadyRef.current = false
      markersRef.current.forEach(({ marker }) => marker.remove())
      markersRef.current = []
      try { map.remove() } catch {}
      mapRef.current = null
      geojsonRef.current = null
    }
  }, [retryTick, rebuildMarkers]) // NO depende de currentUserId/ClanId

  // #3b — Refrescar overlay cuando cambia refreshKey (tras deploy/attack/fortify).
<<<<<<< Front_Ricardo
  // Cada bump dispara su propio fetch; `cancelled` (cleanup) descarta respuestas obsoletas.
=======
  //
  // BUG detectado en la auditoría: el antiguo guard `refreshingRef` serializaba
  // los fetches pero descartaba el segundo bump si venía antes de que terminase
  // el primero. En un fortify `handleSuccess()` bumpea refreshKey y al instante
  // `refreshData()` actualiza `zones` → efecto en MapView vuelve a bumpear
  // refreshKey → el segundo bump llegaba con el primer fetch aún en vuelo y se
  // ignoraba. El primer fetch traía datos (nuevos o viejos según timing de
  // Firestore) y el mapa quedaba con los números cruzados, como denunciaste
  // con Ciutat Fallera ↔ Sant Llorenç.
  //
  // Ahora cada bump dispara su propio fetch. La variable local `cancelled`
  // (seteada por el cleanup del effect anterior cuando llega el nuevo) descarta
  // las respuestas obsoletas, así que el último bump siempre pinta el último.
>>>>>>> main
  useEffect(() => {
    if (refreshKey === 0 || !mapReadyRef.current) return
    const map = mapRef.current
    const gj = geojsonRef.current
    if (!map || !gj) return
    let cancelled = false
    ;(async () => {
      let serverData = []
      try {
        const r = await api.get('/api/v1/state/locations')
        serverData = Array.isArray(r.data) ? r.data : []
      } catch {
        try {
          const r = await api.get('/api/v1/zones/')
          serverData = Array.isArray(r.data) ? r.data : []
        } catch {}
      }
      if (cancelled || !mapRef.current) return
      const enriched = applyServerDataToGeoJSON(gj, serverData, clanIdRef.current, userIdRef.current)
      geojsonRef.current = enriched
      map.getSource('zones')?.setData(enriched)
      rebuildMarkers()
    })()
    return () => { cancelled = true }
  }, [refreshKey, rebuildMarkers])

  // #4 — Recolorear si cambia clan/user sin reinicializar el mapa
  // M-4: produce un nuevo objeto en lugar de mutar geojsonRef.current
  useEffect(() => {
    if (!mapReadyRef.current) return
    const map = mapRef.current
    const gj = geojsonRef.current
    if (!map || !gj) return
    gj.features.forEach(f => {
      const ownerClan = f.properties.ownerClanId
      const ownerUser = f.properties.ownerUserId
      const ownerId = ownerUser || ownerClan
      const isMine =
        (!!currentClanId && ownerClan === currentClanId) ||
        (!!currentUserId && ownerId === currentUserId)
      f.properties.isMine = isMine
      f.properties.color = colorForOwner(ownerId)
    })
    map.getSource('zones')?.setData(gj)
    rebuildMarkers()
  }, [currentClanId, currentUserId, rebuildMarkers])

  // ── View mode switcher — update map paint properties without reinitialising ──
  useEffect(() => {
    if (!mapReadyRef.current || !mapRef.current) return
    const map = mapRef.current
    const battleZoneIds = new Set(battles.map(b => b.zone_id).filter(Boolean))
    const paint = getViewModePaint(viewMode, battleZoneIds)
    try {
      map.setPaintProperty('zones-glow', 'fill-color', paint.fillColor)
      map.setPaintProperty('zones-glow', 'fill-opacity', paint.fillOpacity)
      map.setPaintProperty('zones-border', 'line-color', paint.lineColor)
    } catch {
      // map layers may not be ready yet on first render
    }
  }, [viewMode, battles])

  return (
    <>
      <div className="absolute inset-0">
        <div ref={containerRef} className="absolute inset-0" />
        <div className="up-scanlines" />
      </div>
      {loadError && (
        <div className="absolute inset-0 flex items-center justify-center bg-ink-900/85 z-20 pointer-events-auto">
          <div className="text-center p-6 rounded-2xl border border-neon-pink/40 bg-black/70 backdrop-blur-xl max-w-sm">
            <div className="text-neon-pink font-display text-xl mb-2">⚠ Mapa offline</div>
            <div className="text-white/60 text-sm mb-4">{loadError}</div>
            <button
              onClick={() => setRetryTick(t => t + 1)}
              className="px-4 py-2 rounded-xl bg-neon-pink/20 border border-neon-pink text-neon-pink font-bold"
            >
              Reintentar
            </button>
          </div>
        </div>
      )}
    </>
  )
}

// ─────────────────────────────────────────────────────────────
// Side Action Panel (Deploy / Attack / Fortify)
// ─────────────────────────────────────────────────────────────
function ActionPanel({ kind, zone, onClose, onSuccess, onRefresh }) {
  const { user } = useAuth()
  const [amount, setAmount] = useState(1)
  const [balance, setBalance] = useState(null)
  const [balanceError, setBalanceError] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [myZones, setMyZones] = useState([])      // for fortify: list of owned zones
  const [zonesError, setZonesError] = useState(false)
  const [targetZone, setTargetZone] = useState('') // for fortify: destination zone id
  const [attackResult, setAttackResult] = useState(null)  // { attacker_rolls, defender_rolls, conquered, ... }
  const turn = useTurnPoll()
<<<<<<< Front_Ricardo
=======
  // Contexto del ataque precalculado al abrir el modal: ¿quién defiende la
  // zona?, ¿cuántas tropas tiene?, ¿tengo alguna zona propia adyacente con
  // ≥2 tropas desde la que atacar? Así desactivamos "LANZAR OFENSIVA" antes
  // de que el usuario clique en vano y mostramos info útil DE LA ZONA OBJETIVO
  // (en vez de mi balance de tropas, que en un modal de ataque no pinta nada).
>>>>>>> main
  const [attackContext, setAttackContext] = useState({
    loaded: false, validOrigins: [], targetDefense: 0, targetOwner: null,
  })
  // Gate antes de que el backend rechace el round-trip: leemos /turn/ via
  // el poller compartido. Si no es mi turno, mostramos un banner y
  // desactivamos el botón de acción (evita 403 silenciosos).
  const isMyTurn = !turn || turn.current_player_id === user?.id

  useEffect(() => {
    let cancelled = false
    setBalanceError(false)
    api.get('/api/v1/armies/balance')
      .then(r => { if (!cancelled) setBalance(r.data) })
      .catch(() => { if (!cancelled) setBalanceError(true) })
    if (kind === 'fortify') {
      setZonesError(false)
      api.get('/api/v1/state/locations').then(r => {
        if (cancelled) return
        const owned = (r.data || []).filter(z =>
          z.owner_clan_id && z.id !== zone?.id && (z.total_armies || 0) > 0
        )
        setMyZones(owned)
        if (owned.length > 0) setTargetZone(owned[0].id)
      }).catch(() => { if (!cancelled) setZonesError(true) })
    }
    return () => { cancelled = true }
  }, [kind, zone?.id])

<<<<<<< Front_Ricardo
=======
  // (poller /turn/ centralizado vía useTurnPoll arriba)

>>>>>>> main
  // Precarga del contexto de ataque: una sola vez al abrir el modal sobre
  // una zona enemiga. Si luego cambian las zonas (yo conquisto algo nuevo)
  // el usuario ya habrá cerrado y reabierto el modal, así que no hace falta
  // refrescar esto en un interval.
  //
  // Mantenemos un normalizador (NFD + quitar no-alfanumérico) por seguridad:
  // si en el futuro el backend vuelve a emitir ids incoherentes entre
  // /zones/ y /zones/adjacency, el modal de ataque sigue funcionando sin
  // exigir un hotfix urgente. Con los seeds ya alineados el `fast-path`
  // exacto resuelve siempre en la primera iteración.
  useEffect(() => {
    if (kind !== 'attack' || !zone?.id) return
    let cancelled = false
    Promise.all([
      api.get('/api/v1/zones/adjacency'),
      api.get('/api/v1/zones/'),
    ]).then(([adjRes, zonesRes]) => {
      if (cancelled) return
      const adj = adjRes.data?.adjacency || {}
      const allZones = zonesRes.data || []
      const target = allZones.find(z => z.id === zone.id)

      // Normaliza un id para esquivar el mismatch de slugs del backend.
      // 'zona-l-amistat' y 'zona-lamistat' → 'zonalamistat'; diacríticos fuera.
      const norm = (s) => String(s || '')
        .normalize('NFD').replace(/\p{Diacritic}/gu, '')
        .toLowerCase().replace(/[^a-z0-9]/g, '')

      // Intento 1 (fast path): id exacto.
      let neighborList = adj[zone.id]
      // Intento 2: buscar alguna clave de adj que normalice al mismo valor que
      // la zona que estoy atacando.
      if (!neighborList) {
        const targetNorm = norm(zone.id)
        for (const k of Object.keys(adj)) {
          if (norm(k) === targetNorm) { neighborList = adj[k]; break }
        }
      }
      const neighborIdsRaw = Array.isArray(neighborList) ? neighborList : []
      const neighborsNorm = new Set(neighborIdsRaw.map(norm))

      const myValid = allZones.filter(z =>
        z.owner_clan_id === user?.id &&
        (z.defense_level || 0) >= 2 &&
        neighborsNorm.has(norm(z.id))
      )
      if (import.meta.env.DEV && neighborIdsRaw.length > 0 && myValid.length === 0) {
        // Ayuda a diagnosticar futuros mismatches de slug.
        console.warn('[attack] no valid origins; adj neighbors=', neighborIdsRaw)
      }
      setAttackContext({
        loaded: true,
        validOrigins: myValid,
        targetDefense: Number(target?.total_armies ?? target?.defense_level ?? zone.total_armies ?? zone.defense_level ?? 0),
        targetOwner: target?.owner_clan_id ?? zone.owner_clan_id ?? null,
      })
    }).catch(() => {
      // Si el endpoint falla, dejamos loaded=true con origins vacío pero sin
      // bloquear — el check post-click en handleAction seguirá actuando de
      // red de seguridad.
      if (!cancelled) setAttackContext(s => ({ ...s, loaded: true }))
    })
    return () => { cancelled = true }
  }, [kind, zone?.id, user?.id])

  const max = kind === 'fortify'
    ? Math.max(0, (zone?.total_armies || 1) - 1) // must leave at least 1
    : balance?.armies_available || 1

  const titles = {
    deploy:  { label: 'DESPLEGAR',   icon: Send,   color: '#facc15', desc: `Despliega tropas en ${zone?.name}` },
    attack:  { label: 'ATACAR',      icon: Swords, color: '#f43f5e', desc: `Lanza una ofensiva sobre ${zone?.name}` },
    fortify: { label: 'MOVER TROPAS', icon: Shield, color: '#06b6d4', desc: `Mueve tropas desde ${zone?.name} hacia otro territorio tuyo` },
  }
  const cfg = titles[kind] || titles.deploy
  const Icon = cfg.icon

  const handleAction = async () => {
    if (!zone) return
    // #5 — Guard: zona sin sincronizar con backend → aviso claro
    if (!zone.id || zone._unsynced) {
      setError('Esta zona aún no está sincronizada con el servidor. Prueba a refrescar el mapa.')
      return
    }
    setError(''); setSuccess(''); setLoading(true)
    try {
      if (kind === 'deploy') {
        // Contract endpoint: accepts both {location_id, amount} (legacy) and
        // {location_id, armies} (contract). player_id falls back to JWT sub.
        const r = await api.post('/api/v1/actions/place', { location_id: zone.id, armies: amount })
        setSuccess(r.data?.message || 'Tropas desplegadas.')
      } else if (kind === 'fortify') {
        if (!targetZone) { setError('Selecciona una zona destino'); setLoading(false); return }
        const r = await api.post('/api/v1/armies/fortify', {
          from_location_id: zone.id,
          to_location_id: targetZone,
          amount,
        })
        setSuccess(r.data?.message || 'Tropas movidas correctamente.')
      } else if (kind === 'attack') {
        // Regla Risk: sólo puedes atacar una zona ADYACENTE a una tuya.
        // Antes se duplicaba aquí la lógica de adyacencia (sin el normalizador
        // de slugs) y fallaba para zonas como L'Amistat cuyo id no coincide
        // entre /zones/ y /zones/adjacency. Ahora reutilizamos directamente
        // `attackContext.validOrigins` — lo calcula el efecto que abre el
        // modal (con normalización NFD + quitando no-alfanuméricos) y es la
        // misma fuente que muestra "MIS ADY." en la UI.
        const mineAdjacent = attackContext.validOrigins || []
        if (mineAdjacent.length === 0) {
          setError(
            'No puedes atacar esta zona: no es adyacente a ninguna zona tuya con >=2 tropas. ' +
            'Conquista un barrio vecino primero.'
          )
          setLoading(false); return
        }
        const source = mineAdjacent.reduce((a, b) => (a.defense_level > b.defense_level ? a : b))
        const attacker_dice = Math.min(3, (source.defense_level || 1) - 1)
        const r = await api.post(`/api/v1/zones/${encodeURIComponent(zone.id)}/attack`, {
          from_zone_id: source.id,
          attacker_dice,
        })
        setAttackResult({ ...r.data, source_name: source.name, target_name: zone.name })
        // Refresh map data without closing the panel so the user sees the dice
        onRefresh?.()
        return  // don't call onSuccess — panel stays open until user closes manually
      }
      onSuccess?.()
    } catch (err) {
      setError(err.response?.data?.detail || 'Error en la operacion')
    } finally {
      setLoading(false)
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onClick={onClose}
      className="fixed inset-0 z-[200] flex items-center justify-center p-4"
      style={{ background: 'rgba(2,3,10,0.82)' }}
    >
      <motion.div
        initial={{ scale: 0.85, y: 30 }}
        animate={{ scale: 1, y: 0 }}
        exit={{ scale: 0.85, y: 30 }}
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-md rounded-3xl overflow-hidden border border-white/10"
        style={{
          background: 'linear-gradient(180deg, rgba(20,20,40,0.96), rgba(8,10,20,0.96))',
          boxShadow: `0 20px 60px ${cfg.color}55, 0 0 80px ${cfg.color}33`,
        }}
      >
        <div className="px-6 py-4 flex items-center justify-between border-b border-white/10"
          style={{ background: `linear-gradient(90deg, ${cfg.color}33, transparent)` }}>
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl border" style={{ borderColor: cfg.color, color: cfg.color }}>
              <Icon className="w-5 h-5" />
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-widest font-bold" style={{ color: cfg.color }}>
                {cfg.label}
              </div>
              <h3 className="font-display font-extrabold text-white text-xl">{zone?.name}</h3>
            </div>
          </div>
          <button onClick={onClose} className="p-2 rounded-full hover:bg-white/10">
            <X className="w-4 h-4 text-white/60" />
          </button>
        </div>

        <div className="p-6 space-y-4">
          {kind === 'deploy' && balanceError && (
            <div className="px-4 py-2 rounded-xl bg-yellow-500/10 border border-yellow-500/30 text-yellow-400 text-xs">
              No se pudo cargar tu balance de tropas. El despliegue puede no reflejar tu saldo real.
            </div>
          )}
          {kind === 'deploy' && balance && (
            <div className="grid grid-cols-3 gap-2">
              <div className="rounded-xl p-3 bg-white/5 border border-white/10 text-center">
                <div className="text-[9px] uppercase tracking-widest text-white/50 font-bold">Disponibles</div>
                <div className="text-xl font-display font-extrabold text-white">{balance.armies_available}</div>
              </div>
              <div className="rounded-xl p-3 bg-white/5 border border-white/10 text-center">
                <div className="text-[9px] uppercase tracking-widest text-white/50 font-bold">Hoy</div>
                <div className="text-xl font-display font-extrabold text-white">{balance.armies_earned_today}</div>
              </div>
              <div className="rounded-xl p-3 bg-white/5 border border-white/10 text-center">
                <div className="text-[9px] uppercase tracking-widest text-white/50 font-bold">Total</div>
                <div className="text-xl font-display font-extrabold text-white">{balance.armies_total_earned}</div>
              </div>
            </div>
          )}
          {/* En el modal de ATAQUE las pills útiles son las de la zona OBJETIVO
              (defensa / propietario / zonas mías adyacentes desde las que atacar),
              no mi balance personal — que para Risk da igual, ataco con las
              tropas ya desplegadas en el mapa. */}
          {kind === 'attack' && (() => {
            const ownerNames = {
              'demo-player-001': 'Norte', 'demo-player-002': 'Sur',
              'demo-player-003': 'Este',  'demo-player-004': 'Oeste',
            }
            const ownerColors = {
              'demo-player-001': '#f43f5e', 'demo-player-002': '#facc15',
              'demo-player-003': '#06b6d4', 'demo-player-004': '#a855f7',
            }
            const owner = attackContext.targetOwner
            const ownerLabel = owner ? (ownerNames[owner] || owner.slice(0, 6)) : 'Libre'
            const ownerColor = owner ? (ownerColors[owner] || '#9ca3af') : '#9ca3af'
            const adyCount = attackContext.validOrigins.length
            const adyColor = adyCount > 0 ? '#c8ff00' : '#6b7280'
            return (
              <div className="grid grid-cols-3 gap-2">
                <div className="rounded-xl p-3 bg-white/5 border border-white/10 text-center">
                  <div className="text-[9px] uppercase tracking-widest text-white/50 font-bold">Defensa</div>
                  <div className="text-xl font-display font-extrabold" style={{ color: '#f43f5e' }}>
                    {attackContext.loaded ? attackContext.targetDefense : '—'}
                  </div>
                </div>
                <div className="rounded-xl p-3 bg-white/5 border border-white/10 text-center">
                  <div className="text-[9px] uppercase tracking-widest text-white/50 font-bold">Propietario</div>
                  <div className="text-sm font-display font-extrabold truncate" style={{ color: ownerColor }}>
                    {attackContext.loaded ? ownerLabel : '…'}
                  </div>
                </div>
                <div
                  className="rounded-xl p-3 bg-white/5 border border-white/10 text-center"
                  title="Zonas tuyas adyacentes a este objetivo con ≥2 tropas (desde donde puedes lanzar el ataque)."
                >
                  <div className="text-[9px] uppercase tracking-widest text-white/50 font-bold">Mis Ady.</div>
                  <div className="text-xl font-display font-extrabold" style={{ color: adyColor }}>
                    {attackContext.loaded ? adyCount : '—'}
                  </div>
                </div>
              </div>
            )
          })()}
          {/* Aviso claro cuando no hay ninguna zona mía adyacente con tropas:
              es la razón #1 por la que "no puedo atacar ciertas zonas". Mejor
              pillarlo aquí que en el error post-click. */}
          {kind === 'attack' && attackContext.loaded && attackContext.validOrigins.length === 0 && isMyTurn && (
            <div className="px-4 py-3 rounded-xl bg-yellow-500/10 border border-yellow-500/30 text-yellow-400 text-xs flex items-start gap-2">
              <span className="text-base leading-none">⚠️</span>
              <span>
                No tienes ninguna zona adyacente a ésta con ≥2 tropas. Conquista
                primero un barrio vecino (o refuerza uno que ya toque el objetivo).
              </span>
            </div>
          )}

          <p className="text-white/70 text-sm">{cfg.desc}</p>

          {!isMyTurn && (
            <div className="px-4 py-3 rounded-xl bg-yellow-500/10 border border-yellow-500/30 text-yellow-400 text-xs flex items-start gap-2">
              <span className="text-base leading-none">⏳</span>
              <span>
                No es tu turno. Espera a que {turn?.current_player_id ? `${turn.current_player_id.replace(/^demo-player-/, 'jugador ')} ` : ''}
                termine para {kind === 'attack' ? 'atacar' : kind === 'fortify' ? 'mover tropas' : 'desplegar'}.
              </span>
            </div>
          )}

          {kind === 'deploy' && balance && Number(balance.armies_available || 0) === 0 && (
            <div className="px-4 py-3 rounded-xl bg-neon-cyan/10 border border-neon-cyan/30 text-neon-cyan text-xs flex items-start gap-2">
              <span className="text-base leading-none">🚶</span>
              <span>
                No tienes tropas disponibles. Camina por la ciudad para ganarlas: cada {' '}
                500 pasos ={' '}
                1 army (máx 50 al día).
              </span>
            </div>
          )}

          {/* Fortify: zona origen → zona destino */}
          {kind === 'fortify' && (
            <div className="space-y-2">
              <div className="rounded-xl p-3 border border-white/10 bg-white/5 flex items-center gap-3">
                <Shield className="w-4 h-4 text-neon-cyan flex-shrink-0" />
                <div className="min-w-0">
                  <div className="text-[9px] uppercase tracking-widest text-white/40 font-bold">Origen</div>
                  <div className="font-display font-bold text-white truncate">{zone?.name}</div>
                  <div className="text-[10px] text-white/40">{zone?.total_armies} tropas disponibles</div>
                </div>
              </div>
              <div className="flex items-center justify-center text-white/30 text-sm">▼ mover hacia</div>
              {zonesError ? (
                <div className="rounded-xl p-3 border border-yellow-500/30 bg-yellow-500/10 text-center text-yellow-400 text-sm">
                  No se pudieron cargar tus territorios. Cierra y vuelve a intentarlo.
                </div>
              ) : myZones.length === 0 ? (
                <div className="rounded-xl p-3 border border-white/10 bg-white/5 text-center text-white/40 text-sm">
                  No tienes otros territorios con tropas
                </div>
              ) : (
                <div className="space-y-1.5 max-h-40 overflow-y-auto pr-1">
                  {myZones.map(z => (
                    <button key={z.id} onClick={() => setTargetZone(z.id)}
                      className="w-full rounded-xl p-3 border flex items-center gap-3 transition text-left"
                      style={{
                        borderColor: targetZone === z.id ? '#06b6d4' : 'rgba(255,255,255,0.08)',
                        background: targetZone === z.id ? 'rgba(0,240,255,0.10)' : 'rgba(255,255,255,0.03)',
                      }}>
                      <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: '#06b6d4', boxShadow: targetZone === z.id ? '0 0 8px #06b6d4' : 'none' }} />
                      <div className="flex-1 min-w-0">
                        <div className="font-display font-bold text-white text-sm truncate">{z.name}</div>
                        <div className="text-[10px] text-white/40">{z.total_armies} tropas</div>
                      </div>
                      {targetZone === z.id && <ChevronRight className="w-4 h-4 text-neon-cyan flex-shrink-0" />}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {kind !== 'attack' && (
            <>
              {kind === 'fortify' && max === 0 ? (
                <div className="px-4 py-3 rounded-xl bg-yellow-500/10 border border-yellow-500/30 text-yellow-400 text-sm">
                  Necesitas al menos 2 tropas en este territorio para poder moverlas. Siempre debe quedar 1 de guardia.
                </div>
              ) : (
                <>
                  <div className="flex items-center gap-2">
                    <button onClick={() => setAmount(Math.max(1, amount - 1))}
                      className="w-10 h-10 rounded-xl bg-white/5 border border-white/10 grid place-items-center text-white hover:border-white/30">
                      <Minus className="w-4 h-4" />
                    </button>
                    <input
                      type="number" min="1" max={max} value={amount}
                      onChange={(e) => setAmount(Math.max(1, Math.min(max, parseInt(e.target.value) || 1)))}
                      className="flex-1 py-3 rounded-xl bg-white/5 border border-white/10 text-white text-center font-display font-extrabold text-2xl focus:outline-none focus:border-white/30"
                    />
                    <button onClick={() => setAmount(Math.min(max, amount + 1))}
                      className="w-10 h-10 rounded-xl bg-white/5 border border-white/10 grid place-items-center text-white hover:border-white/30">
                      <Plus className="w-4 h-4" />
                    </button>
                    <button onClick={() => setAmount(max)}
                      className="px-3 py-3 rounded-xl bg-white/5 border border-white/10 text-white text-xs font-display font-bold">
                      MAX
                    </button>
                  </div>
                  <input
                    type="range" min="1" max={max} value={amount}
                    onChange={(e) => setAmount(parseInt(e.target.value))}
                    className="w-full"
                    style={{ accentColor: cfg.color }}
                  />
                  <div className="flex gap-2">
                    {[1, 3, 5, 10].map((q) => (
                      <button key={q} onClick={() => setAmount(Math.min(q, max))}
                        className="flex-1 py-2 rounded-xl border text-xs font-display font-bold transition"
                        style={{
                          borderColor: amount === Math.min(q, max) ? cfg.color : 'rgba(255,255,255,0.1)',
                          color: amount === Math.min(q, max) ? cfg.color : 'rgba(255,255,255,0.6)',
                          background: amount === Math.min(q, max) ? `${cfg.color}22` : 'transparent',
                        }}>
                        +{q}
                      </button>
                    ))}
                  </div>
                </>
              )}
            </>
          )}

          {error && (
            <div className="px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm">
              {error}
            </div>
          )}
          {success && (
            <div className="px-4 py-3 rounded-xl bg-green-500/10 border border-green-500/30 text-green-400 text-sm">
              {success}
            </div>
          )}
          {attackResult && <DiceRollPanel result={attackResult} />}

          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            disabled={
              loading
              || !isMyTurn
              || (kind === 'fortify' && max === 0)
              || (kind === 'deploy' && Number(balance?.armies_available || 0) === 0)
              || (kind === 'attack' && attackContext.loaded && attackContext.validOrigins.length === 0)
            }
            onClick={handleAction}
            className="w-full py-4 rounded-2xl font-display font-bold text-white flex items-center justify-center gap-2 disabled:opacity-50"
            style={{
              background: `linear-gradient(135deg, ${cfg.color}, #a855f7)`,
              boxShadow: `0 8px 24px ${cfg.color}66`,
              color: kind === 'deploy' ? '#06070d' : '#fff',
            }}
          >
            <Icon className="w-5 h-5" />
            {loading ? 'Procesando...' : !isMyTurn ? 'ESPERA TU TURNO' : kind === 'attack' ? `LANZAR OFENSIVA` : `${cfg.label} ${amount} TROPAS`}
          </motion.button>
        </div>
      </motion.div>
    </motion.div>
  )
}


// ─────────────────────────────────────────────────────────────
// WebSocket status indicator — usable in any HUD
// ─────────────────────────────────────────────────────────────
function WsIndicator({ status }) {
  const map = {
    idle:       { color: '#888',    label: 'Inactivo',  pulse: false },
    connecting: { color: '#facc15', label: 'Conectando', pulse: true  },
    open:       { color: '#facc15', label: 'En línea',   pulse: false },
    closed:     { color: '#ff8c2a', label: 'Reconectando…', pulse: true },
    failed:     { color: '#f43f5e', label: 'Sin conexión', pulse: false },
  }
  const s = map[status] || map.idle
  return (
    <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-white/10 backdrop-blur-xl"
      style={{ background: 'rgba(255,255,255,0.04)' }}
      title={`WebSocket: ${s.label}`}>
      <span
        className="w-2 h-2 rounded-full"
        style={{
          background: s.color,
          boxShadow: `0 0 8px ${s.color}`,
          animation: s.pulse ? 'up-heartbeat-pink 1.2s ease-in-out infinite' : 'none',
        }}
      />
      <span className="text-[9px] uppercase tracking-widest font-bold" style={{ color: s.color }}>
        {s.label}
      </span>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────
// Right Panel — Tabs: Misiones | Batallas | Top
// ─────────────────────────────────────────────────────────────
const ICON_MAP = { Footprints, Crown, Swords, Zap, MapIcon: MapIcon, Flame, Target, Trophy }

function RightPanel({ player, clans, missions, battleHistory, leaderboard, zones, loading, onClaimMission, onBattleResolved }) {
  // Tab por defecto: misiones. Antes era 'crews' pero se retiró (el juego
  // es PvP asimétrico de 4 comandantes, no un MMO — no hay gremios).
  const [tab, setTab] = useState('missions')
  const [resolvingId, setResolvingId] = useState(null)
  const [diceResult, setDiceResult] = useState(null) // { battle_id, result, attacker_roll, defender_roll }

  const handleResolve = async (battleId) => {
    setResolvingId(battleId)
    try {
      const r = await api.post(`/api/v1/battles/${battleId}/resolve`)
      setDiceResult(r.data)
      onBattleResolved?.()
    } catch {
      // silently ignore — toast handled globally
    } finally {
      setResolvingId(null)
    }
  }
  // Paleta UNIFICADA estilo Nike: todas las tablas usan el mismo verde
  // Volt (#c8ff00) para contenido. La identidad de cada tab viene de la
  // etiqueta, no del color — así las tarjetas leen 'equipo' en lugar
  // de arco iris.
  const ACCENT = '#c8ff00'  // Volt Nike — el verde 'que se ve blanco'
  const TABS = [
    { id: 'missions', label: 'Misiones', color: ACCENT },
    { id: 'battles',  label: 'Batallas', color: ACCENT },
    { id: 'players',  label: 'Top',      color: ACCENT },
  ]

  return (
    <motion.div
      initial={{ x: 30, opacity: 0 }} animate={{ x: 0, opacity: 1 }} transition={{ delay: 0.1 }}
<<<<<<< Front_Ricardo
      // self-start + justify-start → columna ocupa sólo altura de su
      // contenido y tab bar ancla al top (sin hueco muerto arriba).
      className="col-span-3 w-full flex flex-col justify-start gap-2 self-start"
=======
      // w-full: cuando se usa dentro de un flex-col, self-start colapsaba el
      //   panel al ancho mínimo de su contenido (~250 px frente a los 446 px
      //   del resto de cards de la columna). Forzamos w-full para que ocupe
      //   todo el ancho disponible de la columna padre.
      // col-span-3: conservado por si el componente vuelve a usarse como
      //   hijo directo de un grid en otro lado — es inocuo dentro de flex.
      className="col-span-3 w-full flex flex-col justify-start gap-2"
>>>>>>> main
    >
      {/* Tab bar */}
      <div className="flex gap-1 rounded-xl p-1" style={{ background: 'rgba(255,255,255,0.05)' }}>
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className="flex-1 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-widest transition-all"
            style={tab === t.id
              ? { background: `${t.color}22`, color: t.color, border: `1px solid ${t.color}44` }
              : { color: 'rgba(255,255,255,0.75)', border: '1px solid rgba(255,255,255,0.08)', background: 'rgba(255,255,255,0.05)' }}>
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <AnimatePresence mode="wait">
        {tab === 'missions' && (
          <motion.div key="missions" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }}
            className="rounded-2xl p-4 backdrop-blur-xl border border-white/10 flex-1"
            style={{ background: 'rgba(255,255,255,0.04)' }}>
            <div className="flex items-center gap-2 mb-3">
              <Target className="w-4 h-4" style={{ color: ACCENT }} />
              <h3 className="font-display font-bold text-white text-xs uppercase tracking-widest">Misiones Diarias</h3>
            </div>
            <div className="space-y-2">
              {missions.length === 0 ? (
                <div className="text-xs text-white/30 text-center py-2">Cargando misiones…</div>
              ) : missions.map(m => {
                const Icon = ICON_MAP[m.icon] || Target
                const pct = Math.min(100, (m.progress / m.target) * 100)
                // Ignoramos m.color del backend. Todas las misiones usan el
                // ACCENT (Volt Nike) para un look profesional unificado.
                return (
                  <div key={m.id} className={`rounded-xl p-2.5 border transition ${m.claimed ? 'opacity-40' : ''}`}
                    style={{ background: 'rgba(200,255,0,0.04)', borderColor: 'rgba(200,255,0,0.18)' }}>
                    <div className="flex items-center gap-2 mb-1.5">
                      <Icon className="w-3.5 h-3.5 flex-shrink-0" style={{ color: ACCENT }} />
                      <span className={`flex-1 text-xs text-white font-bold ${m.claimed ? 'line-through' : ''}`}>{m.title}</span>
                      {m.claimable && (
                        <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
                          onClick={() => onClaimMission(m.id)}
                          className="px-2 py-0.5 rounded-lg text-[9px] font-black uppercase tracking-widest"
                          style={{ background: ACCENT, color: '#0a0a0a' }}>
                          +{m.reward_power}p
                        </motion.button>
                      )}
                      {m.claimed && <span className="text-[9px] text-white/30 font-bold">✓ Reclamado</span>}
                      {!m.claimable && !m.claimed && (
                        <span className="text-[9px] font-bold" style={{ color: ACCENT }}>{m.progress}/{m.target}</span>
                      )}
                    </div>
                    {/* Progress bar — Volt unificado */}
                    <div className="h-1 rounded-full bg-white/10 overflow-hidden">
                      <motion.div className="h-full rounded-full"
                        style={{ background: ACCENT }}
                        initial={{ width: 0 }}
                        animate={{ width: `${pct}%` }}
                        transition={{ duration: 0.8, ease: 'easeOut' }} />
                    </div>
                  </div>
                )
              })}
            </div>
          </motion.div>
        )}

        {tab === 'battles' && (
          <motion.div key="battles" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }}
            className="rounded-2xl p-4 backdrop-blur-xl border border-white/10 flex-1"
            style={{ background: 'rgba(255,255,255,0.04)' }}>
            <div className="flex items-center gap-2 mb-3">
              <Swords className="w-4 h-4" style={{ color: ACCENT }} />
              <h3 className="font-display font-bold text-white text-xs uppercase tracking-widest">Historial de Batallas</h3>
            </div>
            <div className="space-y-2">
              {diceResult && (
                <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }}
                  className="rounded-xl px-3 py-2.5 border mb-2"
                  style={{ background: 'rgba(200,255,0,0.06)', borderColor: 'rgba(200,255,0,0.4)' }}>
                  <div className="text-[10px] font-black uppercase tracking-widest mb-1" style={{ color: ACCENT }}>Resultado del dado</div>
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-white/60">Atacante <span className="font-bold" style={{ color: ACCENT }}>{diceResult.attacker_roll}</span></span>
                    <span className="text-white/30">vs</span>
                    <span className="text-white/60">Defensor <span className="font-bold text-white">{diceResult.defender_roll}</span></span>
                  </div>
                  <div className="text-[11px] font-bold mt-1 text-center"
                    style={{ color: diceResult.result === 'attacker_wins' ? ACCENT : 'rgba(255,255,255,0.55)' }}>
                    {diceResult.result === 'attacker_wins' ? '⚔ ¡Ataque exitoso!' : '🛡 Defensa exitosa'}
                  </div>
                  <button onClick={() => setDiceResult(null)}
                    className="text-[9px] text-white/30 hover:text-white/60 w-full text-center mt-1">cerrar</button>
                </motion.div>
              )}
              {battleHistory.length === 0 ? (
                <div className="text-xs text-white/30 text-center py-2">Sin batallas registradas</div>
              ) : battleHistory.map(b => {
                const isAttacker = b.attacker_clan_id === player?.clan_id
                const result = b.result
                const won = (isAttacker && result === 'attacker_wins') || (!isAttacker && result === 'defender_wins')
                const ongoing = result === 'ongoing'
                // Todos los rows usan el ACCENT; el ESTADO se comunica por
                // opacity + label, no por color arcoíris.
                const label = ongoing ? '⚔ En curso' : won ? '✓ Victoria' : '✗ Derrota'
                const labelColor = won ? ACCENT : ongoing ? ACCENT : 'rgba(255,255,255,0.45)'
                const date = b.started_at ? new Date(b.started_at).toLocaleDateString('es-ES', { day: '2-digit', month: '2-digit' }) : ''
                const isResolving = resolvingId === b.id
                return (
                  <div key={b.id}
                    className={`flex items-center gap-2 rounded-xl px-2.5 py-2 border transition ${!won && !ongoing ? 'opacity-55' : ''}`}
                    style={{ background: 'rgba(200,255,0,0.03)', borderColor: 'rgba(200,255,0,0.15)' }}>
                    <span className="text-[9px] font-black uppercase tracking-widest flex-shrink-0" style={{ color: labelColor }}>{label}</span>
                    <div className="flex-1 min-w-0">
                      <div className="text-xs text-white truncate">{b.zone_name || 'Zona'}</div>
                      {b.attacker_rolls?.length > 0 && (
                        <div className="text-[9px] text-white/40">
                          [{b.attacker_rolls.join(',')}] vs [{(b.defender_rolls || []).join(',')}]
                        </div>
                      )}
                    </div>
                    {ongoing ? (
                      <button
                        onClick={() => handleResolve(b.id)}
                        disabled={isResolving}
                        className="text-[9px] font-black uppercase tracking-widest px-2 py-1 rounded-lg transition"
                        style={{
                          background: ACCENT,
                          color: isResolving ? 'rgba(10,10,10,0.4)' : '#0a0a0a',
                        }}>
                        {isResolving ? '…' : 'Resolver'}
                      </button>
                    ) : (
                      <span className="text-[9px] text-white/30">{date}</span>
                    )}
                  </div>
                )
              })}
            </div>
          </motion.div>
        )}

        {tab === 'players' && (
          <motion.div key="players" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }}
            className="rounded-2xl p-4 backdrop-blur-xl border border-white/10 flex-1"
            style={{ background: 'rgba(255,255,255,0.04)' }}>
            <div className="flex items-center gap-2 mb-3">
              <Medal className="w-4 h-4" style={{ color: ACCENT }} />
              <h3 className="font-display font-bold text-white text-xs uppercase tracking-widest">Top Jugadores</h3>
            </div>
            <div className="space-y-2">
              {leaderboard.length === 0 ? (
                <div className="text-xs text-white/30 text-center py-2">Cargando clasificación…</div>
              ) : leaderboard.map((u, i) => {
                const isMe = u.id === player?.id
                const medal = i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : `#${i + 1}`
                // Tu fila se resalta con el ACCENT; el resto queda blanco
                // tenue. Consistente con missions y battles.
                return (
                  <div key={u.id}
                    className={`flex items-center gap-2 rounded-xl px-2.5 py-2 border transition ${isMe ? '' : 'opacity-65'}`}
                    style={{
                      background: isMe ? 'rgba(200,255,0,0.06)' : 'rgba(255,255,255,0.02)',
                      borderColor: isMe ? 'rgba(200,255,0,0.35)' : 'rgba(255,255,255,0.06)',
                    }}>
                    <span className="text-[10px] w-5 text-center flex-shrink-0">{medal}</span>
                    <span className="flex-1 text-xs truncate font-bold"
                      style={{ color: isMe ? ACCENT : '#ffffff' }}>
                      {u.name}{isMe ? ' (tú)' : ''}
                    </span>
                    <span className="text-[10px] font-bold" style={{ color: ACCENT }}>{u.power_points}p</span>
                  </div>
                )
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

/**
 * Imágenes de producto Unsplash (licencia libre) que rotan en las
 * tiles de NikeShoeHero. 3 zapatillas + 3 runners distintos. Cada
 * imagen tiene su caption (nombre del modelo) y un sub (línea
 * descriptiva) estilo ficha de campaña deportiva.
 *
 * Se perdieron en un revert parcial anterior — restauradas aquí.
 */
const SHOE_IMAGES = [
  { src: 'https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=600&q=80&auto=format&fit=crop',
    caption: 'Air Max',  sub: 'Running essentials' },
  { src: 'https://images.unsplash.com/photo-1460353581641-37baddab0fa2?w=600&q=80&auto=format&fit=crop',
    caption: 'Zoom Fly', sub: 'Performance series' },
  { src: 'https://images.unsplash.com/photo-1600185365926-3a2ce3cdb9eb?w=600&q=80&auto=format&fit=crop',
    caption: 'Pegasus',  sub: 'Daily trainer' },
]

const RUNNER_IMAGES = [
  { src: 'https://images.unsplash.com/photo-1571008887538-b36bb32f4571?w=600&q=70&auto=format&fit=crop',
    caption: 'Street pace', sub: 'Find your rhythm' },
  { src: 'https://images.unsplash.com/photo-1552674605-db6ffd4facb5?w=600&q=70&auto=format&fit=crop',
    caption: 'Morning run', sub: 'Own the streets' },
  { src: 'https://images.unsplash.com/photo-1486218119243-13883505764c?w=600&q=70&auto=format&fit=crop',
    caption: 'Sprint drill', sub: 'Explosive speed' },
]

/**
 * ProductCard — tile cuadrado con imagen a borde completo, overlay
 * inferior con caption Archivo Black estilo ficha Nike.
 * Si la imagen no carga (CDN bloqueado / offline), usa el fallback.
 */
function ProductCard({ image, caption, sub, accent = '#c8ff00', fallback = null }) {
  const [failed, setFailed] = useState(false)
  return (
    <div
      className="relative w-full rounded-2xl overflow-hidden border border-white/10 bg-black"
      style={{
        aspectRatio: '1 / 1',
        boxShadow: '0 10px 30px rgba(0,0,0,0.5)',
      }}
    >
      {failed && fallback ? (
        <div className="w-full h-full flex items-center justify-center p-6 bg-[#f6f6f6]">
          {fallback}
        </div>
      ) : (
        <img
          src={image}
          alt={caption}
          className="absolute inset-0 w-full h-full object-cover"
          loading="lazy"
          onError={() => setFailed(true)}
        />
      )}
      <div
        className="absolute inset-x-0 bottom-0 px-3 py-2.5"
        style={{ background: 'linear-gradient(180deg, transparent 0%, rgba(0,0,0,0.85) 100%)' }}
      >
        <div className="font-display text-white text-sm leading-none tracking-nike-tight uppercase">
          {caption}
        </div>
        <div className="text-[9px] uppercase tracking-nike-wide font-bold mt-1"
             style={{ color: accent }}>
          {sub}
        </div>
      </div>
    </div>
  )
}

/**
 * Hero visual del lobby: alterna zapatillas y runners.
 *
 * 2 tiles apilados (shoe + runner) cada uno rota entre 3 imágenes
 * cada 12s para dar variedad sin pesar más.
 */
function NikeShoeHero() {
  const [shoeIdx, setShoeIdx] = useState(() => Math.floor(Math.random() * SHOE_IMAGES.length))
  const [runnerIdx, setRunnerIdx] = useState(() => Math.floor(Math.random() * RUNNER_IMAGES.length))

  useEffect(() => {
    const shoeTimer = setInterval(
      () => setShoeIdx(i => (i + 1) % SHOE_IMAGES.length), 12000
    )
    const runnerTimer = setInterval(
      () => setRunnerIdx(i => (i + 1) % RUNNER_IMAGES.length), 14000   // desfase para que cambien alternando
    )
    return () => { clearInterval(shoeTimer); clearInterval(runnerTimer) }
  }, [])

  const shoe = SHOE_IMAGES[shoeIdx]
  const runner = RUNNER_IMAGES[runnerIdx]

  return (
    <div className="grid grid-cols-2 gap-2 w-full">
      <AnimatePresence mode="wait">
        <motion.div
          key={`shoe-${shoeIdx}`}
          initial={{ opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.96 }}
          transition={{ duration: 0.5 }}
        >
          <ProductCard
            image={shoe.src}
            caption={shoe.caption}
            sub={shoe.sub}
            accent="#facc15"
            fallback={<NeonSneaker />}
          />
        </motion.div>
      </AnimatePresence>
      <AnimatePresence mode="wait">
        <motion.div
          key={`runner-${runnerIdx}`}
          initial={{ opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.96 }}
          transition={{ duration: 0.5 }}
        >
          <ProductCard
            image={runner.src}
            caption={runner.caption}
            sub={runner.sub}
            accent="#f43f5e"
          />
        </motion.div>
      </AnimatePresence>
    </div>
  )
}

/**
 * Panel de progreso personal del jugador + estadísticas de zapatilla.
 *
 * Muestra todo lo relevante de una ficha de running Nike:
 *   1. Estado de conexión (dot pulsante + En línea/Offline)
 *   2. Modelo y tier de zapatilla (derivado del level + steps)
 *   3. Barra de desgaste (0-100% sobre 50k pasos)
 *   4. 3 métricas: distancia km, nivel, días jugando
 *   5. Alerta si el desgaste ≥ 65% — "necesitan descanso"
 *
 * El diseño sigue estética Nike: card negro puro, tipografía Archivo
 * Black para números, labels en uppercase tracking-nike-wide.
 */
function PersonalProgressCard({ player, wsStatus, sneaker }) {
  const STEP_METERS = 0.76
  const totalKm = ((player.steps_total || 0) * STEP_METERS / 1000).toFixed(1)

  // Desgaste de zapatilla — al 100% a los 50k pasos. Es una métrica de
  // "hace cuánto no descansas" más que de fitness real.
  const WEAR_MAX = 50000
  const wearPct = Math.min(100, Math.floor((player.steps_total || 0) / WEAR_MAX * 100))
  const wearColor = wearPct < 30 ? '#facc15' : wearPct < 65 ? '#ff8c2a' : '#f43f5e'
  const wearLabel = wearPct < 30 ? 'Nuevas' : wearPct < 65 ? 'Usadas' : 'Muy usadas'

  let daysPlaying = null
  if (player.created_at) {
    const created = new Date(player.created_at)
    daysPlaying = Math.max(1, Math.floor((Date.now() - created.getTime()) / 86400000))
  }

  const wsMap = {
    idle:       { color: '#6b7280', label: 'Inactivo',   pulse: false },
    connecting: { color: '#facc15', label: 'Conectando', pulse: true  },
    open:       { color: '#facc15', label: 'En línea',   pulse: true  },
    closed:     { color: '#f43f5e', label: 'Offline',    pulse: false },
    error:      { color: '#f43f5e', label: 'Error',      pulse: false },
  }
  const ws = wsMap[wsStatus] || wsMap.idle

  return (
    <div
      className="rounded-2xl p-3 border border-white/10"
      style={{ background: 'rgba(0,0,0,0.7)' }}
    >
      {/* Cabecera: solo modelo zapatilla.
          El 'EN LÍNEA' ya está en el HUD superior (WsIndicator junto a
          los botones tutorial/logout). Mostrarlo aquí también era
          redundante — se eliminó para no duplicar estado. */}
      <div className="mb-3 pb-2 border-b border-white/5">
        <div className="text-[9px] uppercase tracking-nike-wide font-bold text-white/40">
          Mi progreso
        </div>
        <div className="font-display text-white text-sm mt-0.5 tracking-nike-tight uppercase leading-tight">
          {sneaker?.model || 'Street Starter'}
        </div>
      </div>

      {/* Barra de desgaste con gradient de marca
          Volt → blanco → perla. Los 4 colores oficiales en progresión
          (el negro es el track de fondo). Igual que la barra de
          'Progreso de liga' del footer → consistencia total. */}
      <div className="mb-3">
        <div className="flex items-center justify-between mb-1">
          <span className="text-[9px] uppercase tracking-nike-wide font-bold text-white/50">
            Desgaste zapatilla
          </span>
          <span className="text-[10px] font-bold uppercase" style={{ color: '#c8ff00' }}>
            {wearLabel} · {wearPct}%
          </span>
        </div>
        <div className="h-1 rounded-full bg-white/10 overflow-hidden">
          <motion.div
            className="h-full rounded-full"
            style={{
              background: 'linear-gradient(90deg, #c8ff00 0%, #ffffff 55%, #e5e5e5 100%)',
            }}
            initial={{ width: 0 }}
            animate={{ width: `${wearPct}%` }}
            transition={{ duration: 1.2, ease: 'easeOut' }}
          />
        </div>
        {wearPct >= 65 && (
          <div className="mt-1.5 text-[9px] font-bold uppercase tracking-wider" style={{ color: '#e5e5e5' }}>
            ⚠ Necesitan descanso
          </div>
        )}
      </div>

      {/* 3 métricas alineadas en grid */}
      <div className="grid grid-cols-3 gap-2 pt-2 border-t border-white/5">
        <div>
          <div className="font-display text-white text-xl leading-none tracking-nike-tight">
            {totalKm}
          </div>
          <div className="text-[9px] uppercase tracking-nike-wide font-bold text-white/40 mt-1">
            Km totales
          </div>
        </div>
        <div>
          <div className="font-display text-white text-xl leading-none tracking-nike-tight">
            Nv.{player.level || 1}
          </div>
          <div className="text-[9px] uppercase tracking-nike-wide font-bold text-white/40 mt-1">
            Nivel
          </div>
        </div>
        <div>
          <div className="font-display text-white text-xl leading-none tracking-nike-tight">
            {daysPlaying || 1}d
          </div>
          <div className="text-[9px] uppercase tracking-nike-wide font-bold text-white/40 mt-1">
            Jugando
          </div>
        </div>
      </div>
    </div>
  )
}

/**
 * Carrusel de tips de entrenamiento serio — maratón, 5K/10K, nutrición,
 * recuperación, ritmo. Rotan cada 10s. Parafraseado de fuentes reales:
 *
 *   - High5 / marathon-nutrition-plan + how-to-train-for-a-marathon
 *   - marathonhandbook.com
 *   - onepeloton.com — what to eat before a marathon
 *   - mayoclinic.org — 5K training schedule
 *   - strava.com/articles — improve 5K time
 *   - halhigdon.com — 5K training programs
 *
 * Cada tip tiene una categoría (visible como etiqueta de color) para que
 * el lector sepa qué tipo de consejo está recibiendo.
 */
const MARATHON_TIPS = [
  // Entrenamiento — Lucide icons monocromos (se colorean con Volt)
  { cat: 'Entreno', color: '#c8ff00', Icon: Calendar,
    title: '16–20 semanas para tu primer maratón',
    body: 'Los programas clásicos duran entre 16 y 20 semanas. Menos es arriesgado, más se hace eterno. Empieza con 3-4 carreras semanales.' },
  { cat: 'Entreno', color: '#c8ff00', Icon: Repeat,
    title: 'Alterna días duros y suaves',
    body: '2 sesiones intensas a la semana (tirada larga + velocidad) y el resto en ritmo cómodo. El cuerpo crece en los días fáciles.' },
  { cat: 'Entreno', color: '#c8ff00', Icon: Mountain,
    title: 'Añade cuestas una vez por semana',
    body: 'Subir colinas construye fuerza sin la carga de impacto de los sprints en llano. 6-8 repes de 30-60 segundos.' },

  // Ritmo
  { cat: 'Ritmo', color: '#c8ff00', Icon: MessageCircle,
    title: 'El test de la conversación',
    body: 'Durante tus rodajes largos deberías poder mantener una conversación sin jadear. Si no puedes, baja el ritmo.' },
  { cat: 'Ritmo', color: '#c8ff00', Icon: Gauge,
    title: 'Tempo runs suben tu umbral',
    body: 'Corre 20-30 min a un "cómodamente duro" (80-85% de tu máximo). Subirá tu capacidad de mantener ritmos altos.' },
  { cat: 'Ritmo', color: '#c8ff00', Icon: Timer,
    title: 'Intervalos 400/400',
    body: 'Una o dos veces por semana: 400 m fuerte + 400 m trote de recuperación. Repite 6-8 veces. Mejora tu velocidad.' },

  // Nutrición
  { cat: 'Nutrición', color: '#c8ff00', Icon: Utensils,
    title: 'Los hidratos son tu gasolina',
    body: 'En días de entreno duro, 60-70% de tus calorías deberían venir de hidratos. El cuerpo quema ~90-110 kcal por km de running.' },
  { cat: 'Nutrición', color: '#c8ff00', Icon: Pill,
    title: '60-90 g de carbos por hora en carrera',
    body: 'Durante el maratón, ingiere geles o bebidas que te den 60-90 g de carbohidratos cada hora. Probarlos antes en rodajes.' },
  { cat: 'Nutrición', color: '#c8ff00', Icon: Droplet,
    title: 'Carga de hidratos 36-48h antes',
    body: 'Los días previos a la carrera: reduce el entreno y sube la ingesta a 10-12 g de carbos por kg de peso corporal al día.' },

  // Recuperación
  { cat: 'Recuperar', color: '#c8ff00', Icon: Clock,
    title: 'La ventana de 45 minutos',
    body: 'Después de correr, come en los siguientes 45 minutos: ~20 g de proteína + 80 g de carbos. Recupera glucógeno y músculo.' },
  { cat: 'Recuperar', color: '#c8ff00', Icon: Moon,
    title: 'Dormir entrena tanto como correr',
    body: '7-9 horas de sueño profundo es donde ocurre la adaptación real. Sin descanso, el entrenamiento se convierte en lesión.' },
  { cat: 'Recuperar', color: '#c8ff00', Icon: Snowflake,
    title: 'Hielo y masaje los primeros 2 días',
    body: 'Post tirada larga: baño de hielo o piernas en alto 15-20 min. Previene la inflamación que rompe fibras lentas.' },

  // Carrera
  { cat: 'Carrera', color: '#c8ff00', Icon: Flag,
    title: 'Sal controlado en el primer km',
    body: 'Tu corazón pide ir rápido al principio. Ignóralo. Los 5 primeros km deben ir al ritmo objetivo, no por encima.' },
  { cat: 'Carrera', color: '#c8ff00', Icon: Footprints,
    title: 'Estrena zapatillas en el rodaje largo',
    body: 'Jamás corras un maratón con zapatillas nuevas. Usa las de carrera al menos en 2-3 tiradas de 20+ km antes del día D.' },
  { cat: 'Carrera', color: '#c8ff00', Icon: Target,
    title: 'Plan B, C, D',
    body: 'Ten un ritmo objetivo (A), un ritmo aceptable (B) y un ritmo "sólo acabar" (C). Si el calor o la fatiga aprieta, baja al siguiente.' },
]

function MarathonTipsCarousel() {
  const [idx, setIdx] = useState(() => Math.floor(Math.random() * MARATHON_TIPS.length))
  const [paused, setPaused] = useState(false)

  useEffect(() => {
    if (paused) return
    const timer = setInterval(() => {
      setIdx(i => (i + 1) % MARATHON_TIPS.length)
    }, 10000)
    return () => clearInterval(timer)
  }, [paused])

  const tip = MARATHON_TIPS[idx]

  return (
    <div
      className="rounded-2xl p-3 backdrop-blur-xl border flex flex-col"
      style={{ background: 'rgba(255,255,255,0.04)', borderColor: `${tip.color}44` }}
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
    >
      <div className="flex items-center justify-between mb-2">
        <span
          className="text-[9px] uppercase tracking-widest font-bold px-2 py-0.5 rounded-md"
          style={{ background: `${tip.color}22`, color: tip.color, border: `1px solid ${tip.color}55` }}
        >
          {tip.cat}
        </span>
        <span className="text-[9px] text-white/40 font-bold tracking-wider">
          {idx + 1}/{MARATHON_TIPS.length}
        </span>
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          key={idx}
          initial={{ opacity: 0, x: 12 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -12 }}
          transition={{ duration: 0.35 }}
          className="flex gap-2 flex-1"
        >
          {/* Icono Lucide monocromo — coloreado con stroke: currentColor
              + style.color = Volt. Más limpio que emoji colorido. */}
          <div className="flex-shrink-0 pt-0.5" style={{ color: tip.color }}>
            {tip.Icon ? <tip.Icon className="w-5 h-5" strokeWidth={1.8} /> : null}
          </div>
          <div className="flex-1 min-w-0">
            <div
              className="font-bold text-[13px] leading-tight mb-1"
              style={{ color: tip.color }}
            >
              {tip.title}
            </div>
            <div className="text-[11px] text-white/70 leading-relaxed">
              {tip.body}
            </div>
          </div>
        </motion.div>
      </AnimatePresence>

      {/* Progreso + siguiente */}
      <div className="flex items-center gap-2 mt-2 pt-2 border-t border-white/5">
        <div className="flex gap-0.5 flex-1">
          {MARATHON_TIPS.map((_, i) => (
            <span
              key={i}
              className="h-0.5 flex-1 rounded-full transition-colors"
              style={{ background: i === idx ? tip.color : 'rgba(255,255,255,0.1)' }}
            />
          ))}
        </div>
        <button
          type="button"
          onClick={() => setIdx(i => (i + 1) % MARATHON_TIPS.length)}
          className="text-white/60 hover:text-white transition text-xs font-bold"
          aria-label="Siguiente tip"
          title="Siguiente tip"
        >
          →
        </button>
      </div>
    </div>
  )
}

const RUNNING_TIPS = [
  // Icons: Lucide monocromo → se colorean con Volt en el render
  { Icon: TrendingDown, title: 'Empieza más lento de lo que crees',
    body: 'El error #1 de los principiantes es salir a tope. La resistencia se construye con ritmos cómodos y consistentes.' },
  { Icon: Calendar, title: 'Tres sesiones a la semana bastan',
    body: 'Suficiente para progresar sin pasarte de carga. El descanso entre carreras es parte del entrenamiento.' },
  { Icon: Flame, title: 'La constancia supera a la motivación',
    body: 'Aparecer cada día pesa más que correr fuerte un día. La motivación es la chispa; el hábito, el fuego.' },
  { Icon: Footprints, title: 'Deja las zapatillas junto a la puerta',
    body: 'Quita la fricción mental de la mañana: ropa preparada + botella llena = cero excusas para salir.' },
  { Icon: Lightbulb, title: 'Inventa tu mantra',
    body: '"Fuerte y firme", "Puedo con esto"… Repetirlo cuando aprieta reduce la percepción de esfuerzo (estudios lo confirman).' },
  { Icon: MapPin, title: 'Trocea el trayecto',
    body: 'No pienses en los 5 km restantes. Piensa hasta la siguiente farola. Luego la siguiente. Luego la siguiente.' },
  { Icon: Target, title: 'Escribe tu objetivo',
    body: 'Un objetivo concreto puesto donde lo veas cada día es mucho más alcanzable que uno vago en tu cabeza.' },
  { Icon: Users, title: 'Corre con alguien',
    body: 'Clubs de running o apps con amigos: la adherencia sube cuando hay alguien esperándote.' },
  { Icon: Droplet, title: 'Hidrátate antes, durante y después',
    body: 'Una botella visible junto a la puerta recuerda al cuerpo que la carrera empieza con agua, no con el primer kilómetro.' },
  { Icon: Trophy, title: 'Celebra las victorias pequeñas',
    body: 'Cada kilómetro es progreso. No compares con otros: compara con tu "yo" de hace un mes.' },
  { Icon: Bed, title: 'Descansa, que los músculos crecen cuando paras',
    body: 'Dormir bien y no correr todos los días es tan importante como entrenar. El cuerpo se reconstruye fuera de la pista.' },
  { Icon: TrendingUp, title: 'La regla del 10%',
    body: 'No subas tu kilometraje semanal más de un 10% respecto a la semana anterior. Así evitas lesiones por exceso.' },
]

function RunningTipsCarousel() {
  const [idx, setIdx] = useState(() => Math.floor(Math.random() * RUNNING_TIPS.length))
  const [paused, setPaused] = useState(false)

  useEffect(() => {
    if (paused) return
    const timer = setInterval(() => {
      setIdx(i => (i + 1) % RUNNING_TIPS.length)
    }, 8000)
    return () => clearInterval(timer)
  }, [paused])

  const tip = RUNNING_TIPS[idx]

  return (
    <div
      className="rounded-2xl p-4 backdrop-blur-xl border border-white/10 relative overflow-hidden"
      style={{ background: 'rgba(255,255,255,0.04)' }}
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
    >
      <div className="flex items-center gap-2 mb-3">
        <Footprints className="w-4 h-4" style={{ color: '#c8ff00' }} />
        <h3 className="font-display font-bold text-white text-xs uppercase tracking-widest">
          Consejo para runners
        </h3>
        <span className="ml-auto text-[9px] text-white/40 font-bold tracking-wider">
          {idx + 1}/{RUNNING_TIPS.length}
        </span>
      </div>

      {/* Cross-fade al cambiar de tip */}
      <AnimatePresence mode="wait">
        <motion.div
          key={idx}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.35 }}
          className="flex gap-3"
        >
          {/* Icono Lucide monocromo coloreado con Volt — reemplaza emoji */}
          <div className="flex-shrink-0 pt-0.5" style={{ color: '#c8ff00' }}>
            {tip.Icon ? <tip.Icon className="w-6 h-6" strokeWidth={1.8} /> : null}
          </div>
          <div className="flex-1 min-w-0">
            <div className="font-bold text-sm leading-snug mb-1" style={{ color: '#c8ff00' }}>
              {tip.title}
            </div>
            <div className="text-xs text-white/70 leading-relaxed">
              {tip.body}
            </div>
          </div>
        </motion.div>
      </AnimatePresence>

      {/* Dots de progreso + flecha siguiente */}
      <div className="flex items-center gap-2 mt-3 pt-3 border-t border-white/5">
        <div className="flex gap-1 flex-1">
          {RUNNING_TIPS.map((_, i) => (
            <span
              key={i}
              className="h-0.5 flex-1 rounded-full transition-colors"
              style={{ background: i === idx ? '#c8ff00' : 'rgba(255,255,255,0.1)' }}
            />
          ))}
        </div>
        <button
          type="button"
          onClick={() => setIdx(i => (i + 1) % RUNNING_TIPS.length)}
          className="text-white/60 hover:text-neon-cyan transition text-xs font-bold"
          aria-label="Siguiente consejo"
          title="Siguiente consejo"
        >
          →
        </button>
      </div>
    </div>
  )
}

function Dashboard({ player, onStartRun, onClaim, claimed, claiming = false, onLogout, clans, zones, battles, onRefresh, loading = false, wsStatus = 'idle', missions = [], battleHistory = [], leaderboard = [], onClaimMission, onReopenTutorial }) {
  const [claimReward, setClaimReward] = useState(null)
  const [burst, setBurst] = useState([])

  // El botón "Jugar turnos de bots" vive ahora en el HUD del mapa
  // (SimulateBotsButton, junto al TurnBanner/EndTurnButton). Aquí en el
  // lobby no pinta nada: cuando estás en el Dashboard aún no ha empezado
  // la partida en el sentido visual del mapa.

  // Contadores del HUD: usamos el total real de zonas del backend (86 en v3)
  // en vez del cap artificial de 49 que teníamos antes — con setup inicial
  // hay 60 ocupadas (15×4) y el cap dejaba LIBRES en 0 por el max(0, 49-60).
  const conquered = zones.filter(z => z.owner_clan_id).length
  const unclaimed = zones.filter(z => !z.owner_clan_id).length
  const xpPct = Math.min(100, (player.power_points / 1000) * 100)

  // Zapatilla — desgaste. El desgaste se comunica por LUMINANCIA, no por
  // cambio de matiz. Todos los estados usan Volt como único color; la
  // intensidad del "alerta" sube con desgaste mayor (más saturado).
  // Alternativa antes: cambio rojo/naranja/lima — múltiples colores.
  const WEAR_MAX_STEPS = 50000
  const wearPct = Math.min(100, Math.floor((player.steps_total / WEAR_MAX_STEPS) * 100))
  const wearColor = wearPct < 65 ? '#c8ff00' : '#ffffff'   // blanco = alerta inversa (borrar)
  const wearLabel = wearPct < 30 ? 'Nueva' : wearPct < 65 ? 'Usada' : 'Muy usada'

  // Sneaker tiers — todos usan paleta marca (Volt / blanco / perla).
  const SNEAKER_TIERS = [
    { minLevel: 1,  minSteps:      0, model: 'Street Starter',  tier: 'Principiante', tierColor: '#e5e5e5' },
    { minLevel: 3,  minSteps:   5000, model: 'Urban Runner II', tier: 'Amateur',      tierColor: '#e5e5e5' },
    { minLevel: 5,  minSteps:  15000, model: 'Asphalt Pro',     tier: 'Avanzado',     tierColor: '#ffffff' },
    { minLevel: 8,  minSteps:  30000, model: 'Neon Racer X',    tier: 'Élite',        tierColor: '#c8ff00' },
    { minLevel: 12, minSteps:  60000, model: 'Phantom Ultra',   tier: 'Leyenda',      tierColor: '#c8ff00' },
  ]
  const sneaker = [...SNEAKER_TIERS].reverse().find(
    t => (player.level || 1) >= t.minLevel && (player.steps_total || 0) >= t.minSteps
  ) || SNEAKER_TIERS[0]

  const handleClaim = async () => {
    const reward = await onClaim()
    if (reward) {
      setClaimReward(reward)
      setTimeout(() => setClaimReward(null), 5000)
      // Burst particles — 8 radial projectiles. Símbolos limpios (sin
      // emojis coloridos) y paleta unificada: Volt + blanco + perla.
      const EMOJIS = ['+', '✦', '●', '+', '✦', '●', '+', '✦']
      const COLORS = ['#c8ff00', '#ffffff', '#e5e5e5', '#c8ff00', '#ffffff', '#e5e5e5', '#c8ff00', '#ffffff']
      setBurst(Array.from({ length: 8 }, (_, i) => {
        const angle = (i / 8) * Math.PI * 2
        const dist = 60 + Math.random() * 40
        return {
          id: i,
          x: Math.cos(angle) * dist,
          y: -(Math.abs(Math.sin(angle)) * dist + 30),
          text: EMOJIS[i],
          color: COLORS[i],
          delay: i * 0.07,
        }
      }))
      setTimeout(() => setBurst([]), 2200)
    }
  }

  return (
    <motion.div
      key="dashboard"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="absolute inset-0 flex flex-col overflow-hidden"
    >
      <NeonGrid />
      <RunnerParade />

      {/* Claim reward toast */}
      <AnimatePresence>
        {claimReward && (
          <motion.div initial={{ y: -60, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: -60, opacity: 0 }}
            className="fixed top-6 left-1/2 -translate-x-1/2 z-50 px-6 py-3 rounded-2xl font-display font-bold text-sm flex items-center gap-3"
            style={{
              background: '#c8ff00',
              color: '#0a0a0a',
              boxShadow: '0 8px 30px rgba(200,255,0,0.4)',
            }}>
            <Gift className="w-5 h-5" />
            {claimReward}
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── HEADER ── */}
      <header className="relative z-10 flex items-center justify-between px-10 pt-7 pb-4">
        {/* Left: avatar + nombre + nivel — paleta marca blanco/Volt */}
        <div className="flex items-center gap-4">
          <div className="relative">
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 16, repeat: Infinity, ease: 'linear' }}
              className="absolute -inset-1 rounded-full"
              style={{ background: 'conic-gradient(#c8ff00, #ffffff, #e5e5e5, #c8ff00)', filter: 'blur(2px)' }}
            />
            <div className="relative w-12 h-12 rounded-full bg-[#0a0a0a] grid place-items-center border-2 border-[#0a0a0a]">
              <Footprints className="w-6 h-6 text-white" strokeWidth={1.5} />
            </div>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <NameEditor fallback={player.name} />
              <span
                className="px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-widest"
                style={{
                  background: 'rgba(200,255,0,0.15)',
                  border: '1px solid rgba(200,255,0,0.45)',
                  color: '#c8ff00',
                }}
              >
                Nv.{player.level || 1}
              </span>
            </div>
            <div className="flex items-center gap-2 mt-1.5">
              <div className="w-32 h-1.5 rounded-full bg-white/10 overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${xpPct}%` }}
                  transition={{ duration: 1.2, delay: 0.3 }}
                  className="h-full"
                  style={{ background: 'linear-gradient(90deg, #c8ff00 0%, #ffffff 100%)' }}
                />
              </div>
              <span className="text-[10px] text-white/40 font-mono">{player.power_points} XP</span>
            </div>
          </div>
        </div>

        {/* Right: WS indicator + tutorial help + logout */}
        <div className="flex items-center gap-2">
          <WsIndicator status={wsStatus} />
          <button
            onClick={onReopenTutorial}
            title="Ver tutorial"
            className="p-2 rounded-full backdrop-blur-xl border border-white/10 hover:border-neon-lime text-white/40 hover:text-neon-lime transition"
            style={{ background: 'rgba(255,255,255,0.04)' }}
          >
            <BookOpen className="w-4 h-4" />
          </button>
          <button onClick={onLogout}
            className="p-2 rounded-full backdrop-blur-xl border border-white/10 hover:border-neon-pink text-white/40 hover:text-neon-pink transition"
            style={{ background: 'rgba(255,255,255,0.04)' }}>
            <Power className="w-4 h-4" />
          </button>
        </div>
      </header>

      {/* ── MAIN GRID ──
          overflow-hidden + min-h-0 garantizan que los hijos no se
          'escapen' visualmente por debajo (que era la causa del
          'Guerrero' pegándose al footer). */}
      <main className="relative z-10 flex-1 grid grid-cols-12 gap-4 px-10 pb-4 min-h-0 overflow-hidden">

        {/* LEFT — zapatilla + marchar */}
        <motion.div
          initial={{ x: -30, opacity: 0 }} animate={{ x: 0, opacity: 1 }} transition={{ delay: 0.1 }}
          className="col-span-3 flex flex-col justify-center gap-3"
        >
          {/* Product shot estilo Nike: imagen real de zapatilla running
              sobre fondo gris claro (#f6f6f6, el gris-producto de nike.com).
              Si la imagen no carga (offline / CORS) caemos al SVG NeonSneaker
              como fallback para no dejar un hueco. */}
          <NikeShoeHero />

          {/* Panel de progreso personal — reemplaza el desgaste de zapatilla.
              Info real y útil: conexión, distancia acumulada, nivel, días jugando. */}
          <PersonalProgressCard player={player} wsStatus={wsStatus} sneaker={sneaker} />

          {/* Carrusel de tips de entrenamiento — maratón, 5K/10K, nutrición,
              recuperación, ritmo. Rotan cada 10s. Diferente del carrusel
              de 'motivación general' que está en la columna derecha. */}
          <MarathonTipsCarousel />

        </motion.div>

        {/* CENTER — hero player */}
        <motion.div
          initial={{ y: 30, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ delay: 0.15 }}
          className="col-span-6 flex flex-col items-center justify-center gap-6"
        >
          {/* HERO HEADLINE Nike-style — responsive.
              Tamaño controlado con clamp(min, fluid, max) — 2rem en móvil,
              5vw fluido, 4.5rem como tope máximo en desktop. Ya no se
              desborda porque max está muy por debajo del ancho del container. */}
          <div className="text-center select-none w-full">
            <div
              className="font-display text-white leading-[0.88] tracking-nike-tight"
              style={{ fontSize: 'clamp(2rem, 5.5vw, 4.5rem)' }}
            >
              <div>CONQUISTA</div>
              <div>VALENCIA</div>
              <div className="text-neon-lime">CORRIENDO.</div>
            </div>
            <div className="mt-3 text-[10px] uppercase tracking-nike-wide font-bold text-white/40">
              Urban Pacer · CloudRISK
            </div>
          </div>

          {/* Zona conquistada counter — más contenido, Nike-style minimal */}
          <div className="flex items-center gap-8">
            {[
              { label: 'Zonas', val: conquered, icon: Crown },
              { label: 'Libres', val: unclaimed, icon: MapIcon },
              { label: 'Batallas', val: battles.length, icon: Swords },
            ].map(({ label, val, icon: Icon }) => (
              <div key={label} className="flex flex-col items-center gap-0.5">
                <div className="flex items-center gap-1.5">
                  <Icon className="w-3 h-3 text-white/60" />
                  <span className={`font-display text-xl text-white ${loading ? 'animate-pulse' : ''}`}>
                    {loading ? '—' : val}
                  </span>
                </div>
                <span className="text-[9px] uppercase tracking-nike-wide font-bold text-white/40">{label}</span>
              </div>
            ))}
          </div>

          {/* CTAs Nike-style: ambos son píldoras sólidas blancas. Se
              diferencian sólo por el icono (Play vs BookOpen). No hay
              'variant secundario' porque confunde al usuario. */}
          <div className="flex flex-wrap items-center gap-3 justify-center">
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={onStartRun}
              className="px-8 py-3.5 rounded-full bg-white text-black font-bold text-[13px] uppercase tracking-nike-wide
                         hover:bg-neon-lime transition-colors duration-200
                         flex items-center gap-2"
            >
              <Play className="w-4 h-4 fill-black" />
              Jugar ahora
            </motion.button>
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={onReopenTutorial}
              className="px-8 py-3.5 rounded-full bg-white text-black font-bold text-[13px] uppercase tracking-nike-wide
                         hover:bg-neon-lime transition-colors duration-200
                         flex items-center gap-2"
            >
              <BookOpen className="w-4 h-4" />
              Cómo jugar
            </motion.button>
          </div>

          {/* Reward chest + CTA tipográfico Nike-style */}
          <div className="relative flex flex-col items-center gap-5 mt-6">
            <Shoebox onClick={handleClaim} claimed={claimed} />
            {!claimed && (
              <motion.div
                animate={{ opacity: [0.75, 1, 0.75] }}
                transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
                className="flex flex-col items-center gap-2 pointer-events-none mt-2"
              >
                {/* Tipografía Nike: font-display (Archivo Black) uppercase
                    tracking-nike-wide, sin glow amarillo exagerado. */}
                <span
                  className="font-display text-base text-white tracking-nike-wide uppercase whitespace-nowrap"
                  style={{ letterSpacing: '0.22em' }}
                >
                  Toca para reclamar
                </span>
                {/* Línea sutil Volt debajo — acento de marca */}
                <span
                  className="block h-[2px] w-8 rounded-full"
                  style={{ background: '#c8ff00' }}
                />
              </motion.div>
            )}
            {claimed && (
              <span className="font-display text-xs text-white/40 tracking-nike-wide uppercase"
                    style={{ letterSpacing: '0.22em' }}>
                Reclamado
              </span>
            )}
          </div>
        </motion.div>

        {/* RIGHT — lobby (4 fixed players) + misiones */}
        <motion.div
          initial={{ x: 30, opacity: 0 }} animate={{ x: 0, opacity: 1 }} transition={{ delay: 0.1 }}
          className="col-span-3 flex flex-col justify-center gap-3"
        >
          {/* Lobby of 4 fixed commanders — replaces the old Crews panel. */}
          <div className="rounded-2xl p-4 backdrop-blur-xl border border-white/10 flex-1"
            style={{ background: 'rgba(255,255,255,0.04)' }}>
            <div className="flex items-center gap-2 mb-3">
              <Trophy className="w-4 h-4 text-neon-lime" />
              <h3 className="font-display font-bold text-white text-xs uppercase tracking-widest">Lobby · 4 comandantes</h3>
            </div>
            <div className="space-y-2">
              {[
                { id: 'demo-player-001', name: getNorteName(), color: '#f43f5e', isMe: true },
                { id: 'demo-player-002', name: 'Comandante Sur',    color: '#facc15' },
                { id: 'demo-player-003', name: 'Comandante Este',   color: '#06b6d4' },
                { id: 'demo-player-004', name: 'Comandante Oeste',  color: '#a855f7' },
              ].map((c) => (
                <div key={c.id} className={`flex items-center gap-2 ${c.id === player?.id ? 'opacity-100' : 'opacity-70'}`}>
                  <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: c.color, boxShadow: `0 0 6px ${c.color}` }} />
                  <span className={`flex-1 text-xs truncate ${c.id === player?.id ? 'text-neon-lime font-bold' : 'text-white'}`}>
                    {c.name}
                  </span>
                  <span className="text-[9px] uppercase text-white/40 font-bold tracking-wider">
                    {c.id === player?.id ? 'Tú' : 'online'}
                  </span>
                </div>
              ))}
            </div>

          </div>

<<<<<<< Front_Ricardo
=======
          {/* RightPanel: tabs Misiones | Batallas | Top.
              Sustituye a la mini-card hardcoded de 3 misiones falsas que
              había aquí antes — ahora muestra las 5 misiones reales del
              backend, el historial de batallas y el leaderboard. Antes este
              panel se renderizaba como un 4.º `col-span-3` en el grid y
              hacía wrap a una segunda fila FUERA del viewport (main tiene
              overflow-hidden), quedando invisible para el usuario. */}
>>>>>>> main
          <RightPanel
            player={player}
            clans={clans}
            missions={missions}
            battleHistory={battleHistory}
            leaderboard={leaderboard}
            zones={zones}
            loading={loading}
            onClaimMission={onClaimMission}
            onBattleResolved={onRefresh}
          />

          {/* Consejos para runners — carrusel rotativo de 12 tips */}
          <RunningTipsCarousel />
        </motion.div>
      </main>

      {/* ── FOOTER STATS BAR ──
          flex-shrink-0 evita que se comprima por el flex-1 del main;
          mt-auto lo empuja al fondo si el main quedara más corto.
          Fondo casi opaco (rgba 0,0,0,0.95) oculta cualquier bleeding
          del contenido superior. Shadow superior crea separación
          visual clara con el main. */}
      <footer className="relative z-20 flex-shrink-0 mt-auto px-6 pb-5 pt-4">
        <motion.div
          initial={{ y: 20, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ delay: 0.3 }}
          className="rounded-2xl px-6 py-3 border flex items-center justify-between"
          style={{
            background: 'rgba(0,0,0,0.95)',
            borderColor: 'rgba(255,255,255,0.08)',
            boxShadow: '0 -8px 24px rgba(0,0,0,0.55), 0 0 0 1px rgba(0,0,0,0.6)',
          }}
        >
          <div className="flex items-center gap-2 text-[10px] uppercase tracking-nike-wide text-white/50 font-bold">
            <TrendingUp className="w-3 h-3" style={{ color: '#c8ff00' }} />
            Progreso de liga
          </div>
          {/* Barra Nike: de Volt (arranque con energía) pasa a blanco
              y termina en perla — los 4 colores de marca menos el
              negro (que es el track de fondo). */}
          <div className="flex-1 mx-6 h-1.5 rounded-full overflow-hidden"
               style={{ background: 'rgba(255,255,255,0.10)' }}>
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${xpPct}%` }}
              transition={{ duration: 1.5, delay: 0.5 }}
              className="h-full"
              style={{
                background: 'linear-gradient(90deg, #c8ff00 0%, #ffffff 55%, #e5e5e5 100%)',
              }}
            />
          </div>
          {/* Stats: Poder en Volt (es el 'currency' principal), Monedas
              y Pasos en blanco/perla. Unifica con la paleta de marca. */}
          <div className="flex items-center gap-6">
            {[
              { label: 'Poder',   val: player.power_points,              color: '#c8ff00' },
              { label: 'Monedas', val: player.gold,                      color: '#ffffff' },
              { label: 'Pasos',   val: player.steps_total?.toLocaleString(), color: '#e5e5e5' },
            ].map(({ label, val, color }) => (
              <div key={label} className="flex flex-col items-center">
                <span className="font-display font-extrabold text-sm" style={{ color }}>{val}</span>
                <span className="text-[9px] uppercase tracking-nike-wide text-white/30 font-bold">{label}</span>
              </div>
            ))}
          </div>
        </motion.div>
      </footer>
    </motion.div>
  )
}

// ─────────────────────────────────────────────────────────────
// ENVIRONMENT BANNER — live air × weather multiplier from /api/v1/multipliers
// ─────────────────────────────────────────────────────────────
// ─────────────────────────────────────────────────────────────
// DICE ROLL PANEL — shown inside the Attack modal after combat resolves
// ─────────────────────────────────────────────────────────────
// Unicode dice faces funcionan en casi todas las fuentes del sistema y se
// ven muy limpios — más legibles que pips pintados con divs a este tamaño.
const DICE_FACES = ['', '⚀', '⚁', '⚂', '⚃', '⚄', '⚅']

/**
 * Dado animado estilo Risk.
 *  - Durante 700ms rota rápido y cambia la cara cada 60ms (efecto tumbling).
 *  - Al aterrizar hace un bounce con scale 1.25 → 1.0 + flash del color.
 *  - `delay` permite stagger entre dados consecutivos.
 */
function Die({ value, color = '#ffffff', delay = 0 }) {
  const [shown, setShown] = useState(1)
  const [rolling, setRolling] = useState(true)
  const [landed, setLanded] = useState(false)

  useEffect(() => {
    setRolling(true); setLanded(false)
    const t0 = setTimeout(() => {
      let tick = 0
      const id = setInterval(() => {
        tick++
        setShown(Math.floor(Math.random() * 6) + 1)
        if (tick > 11) {
          clearInterval(id)
          setShown(value)
          setRolling(false)
          setLanded(true)
          setTimeout(() => setLanded(false), 420)
        }
      }, 58)
      return () => clearInterval(id)
    }, delay)
    return () => clearTimeout(t0)
  }, [value, delay])

  return (
    <motion.div
      animate={{
        rotate: rolling ? [0, 180, 360, 540, 720] : 0,
        scale: landed ? [1.0, 1.28, 0.95, 1.0] : 1.0,
      }}
      transition={{
        rotate: { duration: rolling ? 0.72 : 0, ease: 'easeOut' },
        scale:  { duration: landed ? 0.42 : 0,  times: [0, 0.3, 0.7, 1], ease: 'easeOut' },
      }}
      className="w-14 h-14 rounded-xl border-2 flex items-center justify-center text-4xl font-black select-none"
      style={{
        borderColor: color,
        color,
        textShadow: `0 0 12px ${color}, 0 0 24px ${color}66`,
        background: landed ? `${color}22` : 'rgba(0,0,0,0.4)',
        boxShadow: landed
          ? `0 0 24px ${color}99, inset 0 0 12px ${color}44`
          : `0 4px 12px rgba(0,0,0,0.6)`,
        transition: 'background 0.3s, box-shadow 0.3s',
      }}
    >
      {DICE_FACES[shown] || '·'}
    </motion.div>
  )
}

function DiceRollPanel({ result }) {
  const { attacker_rolls = [], defender_rolls = [], conquered, attacker_losses, defender_losses } = result
  return (
    <motion.div
      initial={{ scale: 0.8, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      className="px-4 py-4 rounded-xl border bg-black/70 space-y-3"
      style={{ borderColor: conquered ? '#facc15' : '#f43f5e' }}
    >
      <div className="text-center text-xs uppercase tracking-widest text-white/50 font-bold">
        Tirada de dados
      </div>
      <div className="flex items-center justify-around">
        <div className="flex flex-col items-center gap-2">
          <span className="text-[10px] uppercase text-neon-pink font-bold">Atacante</span>
          <div className="flex gap-2">
            {attacker_rolls.length > 0
              ? attacker_rolls.map((v, i) => <Die key={i} value={v} color="#f43f5e" delay={i * 80} />)
              : <span className="text-xs text-white/40">sin tirada</span>}
          </div>
          {attacker_losses > 0 && (
            <span className="text-[10px] text-red-400 font-bold">−{attacker_losses} tropa{attacker_losses > 1 ? 's' : ''}</span>
          )}
        </div>
        <div className="text-xl text-white/30">vs</div>
        <div className="flex flex-col items-center gap-2">
          <span className="text-[10px] uppercase text-neon-cyan font-bold">Defensor</span>
          <div className="flex gap-2">
            {defender_rolls.length > 0
              ? defender_rolls.map((v, i) => <Die key={i} value={v} color="#06b6d4" delay={300 + i * 80} />)
              : <span className="text-xs text-white/40">zona desierta</span>}
          </div>
          {defender_losses > 0 && (
            <span className="text-[10px] text-red-400 font-bold">−{defender_losses} tropa{defender_losses > 1 ? 's' : ''}</span>
          )}
        </div>
      </div>
      <div
        className="text-center font-display font-extrabold text-lg uppercase"
        style={{ color: conquered ? '#facc15' : '#f43f5e' }}
      >
        {conquered ? '⚑ Zona conquistada' : '⚔ La zona resiste'}
      </div>
    </motion.div>
  )
}

// ─────────────────────────────────────────────────────────────
// TURN BANNER — "Tu turno" when it's your player, otherwise who plays
// ─────────────────────────────────────────────────────────────
// ── Nombre personalizado del jugador humano (Norte) ──────────────────────────
// Se guarda en localStorage para persistir entre sesiones.
const PLAYER_NAME_KEY = 'cloudrisk_player_name'
function getNorteName() {
  return localStorage.getItem(PLAYER_NAME_KEY) || 'Norte'
}

function NameEditor({ fallback }) {
  const stored = localStorage.getItem(PLAYER_NAME_KEY)
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState(stored || fallback || 'Norte')

  const save = (val) => {
    const v = val.trim() || fallback || 'Norte'
    setName(v)
    localStorage.setItem(PLAYER_NAME_KEY, v)
    setEditing(false)
  }

  if (editing) return (
    <input
      autoFocus
      className="font-display font-extrabold text-white text-lg bg-transparent border-b-2 outline-none w-44"
      style={{ borderColor: '#c8ff00' }}
      value={name}
      onChange={e => setName(e.target.value)}
      onBlur={e => save(e.target.value)}
      onKeyDown={e => {
        if (e.key === 'Enter') save(name)
        if (e.key === 'Escape') setEditing(false)
      }}
    />
  )

  return (
    <button onClick={() => setEditing(true)} className="flex items-center gap-2 group text-left">
      <span className="font-display font-extrabold text-white text-lg leading-none">{name}</span>
      <span
        className="text-[9px] font-black px-1.5 py-0.5 rounded uppercase tracking-widest"
        style={{ background: 'rgba(200,255,0,0.18)', color: '#c8ff00', border: '1px solid rgba(200,255,0,0.35)' }}
      >
        Yo ✏
      </span>
    </button>
  )
}

function TurnBanner({ myUserId }) {
  const turn = useTurnPoll()

  if (!turn) return null
  const mine = turn.current_player_id === myUserId
  const p = PLAYERS[turn.current_player_id]
  const who = turn.current_player_id === 'demo-player-001'
    ? getNorteName()
    : (p?.name || turn.current_player_id.slice(0, 8))
<<<<<<< Front_Ricardo
=======
  // Mi turno → verde lima; turno de un rival → color del rival (así
  // el jugador asocia el banner al color del bot que juega ahora).
>>>>>>> main
  const tone = mine ? '#facc15' : (p?.color || '#f43f5e')
  return (
    <div
      className="px-4 py-2.5 rounded-full backdrop-blur-xl border bg-black/70 flex items-center gap-2 font-bold text-sm"
      style={{ borderColor: `${tone}77`, color: tone }}
    >
      <span className="w-2 h-2 rounded-full" style={{ background: tone, boxShadow: `0 0 8px ${tone}` }} />
      {mine ? (
        <>
          <span>Tu turno</span>
          <span className="text-xs text-white/40 uppercase">· {turn.phase}</span>
        </>
      ) : (
        <>
          <span className="text-white/70">Turno de</span>
          <span>{who}</span>
        </>
      )}
      <span className="text-[10px] text-white/30">#{turn.turn_number}</span>
    </div>
  )
}

/**
 * Pill persistente con la info de tropas del jugador.
 * Siempre visible en pantalla. Se refresca cada 3s por si cambian los
 * turnos / otros jugadores nos atacan / gana steps.
 *
 * Muestra:
 *   DISPONIBLES — power_points listas para desplegar (pool + steps + bonus turno)
 *   BONUS PRÓX. — max(3, zones/3) que recibiré al acabar esta vuelta
 *   EN MAPA    — total de tropas en mis zonas ahora mismo (defensa activa)
 */
function TroopsReadout({ zones = [], currentUserId, myColor = '#facc15' }) {
  const [reinf, setReinf] = useState(null)
  useEffect(() => {
    let alive = true
    const fetchOnce = async () => {
      try {
        const r = await api.get('/api/v1/turn/reinforcements')
        if (alive) setReinf(r.data)
      } catch { /* ignore */ }
    }
    fetchOnce()
    const id = setInterval(fetchOnce, 3000)
    return () => { alive = false; clearInterval(id) }
  }, [])

  // Tropas en mapa = Σ defense_level en zonas que son mías
  const deployedAll = zones
    .filter(z => z.owner_clan_id === currentUserId)
    .reduce((s, z) => s + (z.total_armies || z.defense_level || 0), 0)

  const available = reinf?.available_now ?? 0
  const nextBonus = reinf?.next_turn_zone_bonus ?? 0
  const zonesOwned = reinf?.zones_owned ?? 0

  return (
    <div
      className="pointer-events-auto fixed bottom-6 left-1/2 -translate-x-1/2 z-30 flex items-stretch gap-0 rounded-2xl border backdrop-blur-xl overflow-hidden"
      style={{
        background: 'rgba(6,7,16,0.88)',
        borderColor: `${myColor}55`,
        boxShadow: `0 10px 32px rgba(0,0,0,0.6), 0 0 24px ${myColor}22`,
      }}
      title="Tus tropas — refresco cada 3 s"
    >
      <div className="px-5 py-3 flex flex-col items-center border-r border-white/5">
        <span className="text-[9px] uppercase tracking-widest font-bold opacity-60" style={{ color: myColor }}>
          Disponibles
        </span>
        <span className="font-display font-extrabold text-2xl" style={{ color: myColor, textShadow: `0 0 12px ${myColor}` }}>
          {available}
        </span>
      </div>
      <div className="px-5 py-3 flex flex-col items-center border-r border-white/5">
        <span className="text-[9px] uppercase tracking-widest font-bold text-white/50">
          En mapa
        </span>
        <span className="font-display font-extrabold text-2xl text-white">
          {deployedAll}
        </span>
      </div>
      <div className="px-5 py-3 flex flex-col items-center">
        <span className="text-[9px] uppercase tracking-widest font-bold text-white/50">
          Próx. turno
        </span>
        <span className="font-display font-extrabold text-2xl text-white/80">
          +{nextBonus}
        </span>
        <span className="text-[8px] text-white/30 mt-0.5">
          {zonesOwned} zonas
        </span>
      </div>
    </div>
  )
}

function EndTurnButton({ myUserId }) {
  const turn = useTurnPoll()
  const [busy, setBusy] = useState(false)
  const mine = !!turn && turn.current_player_id === myUserId

  const end = useCallback(async () => {
    setBusy(true)
    try { await api.post('/api/v1/turn/end') } finally { setBusy(false) }
  }, [])

<<<<<<< Front_Ricardo
  // Atajo de teclado: Enter termina el turno cuando es el mío y no hay input con foco.
=======
  // Atajo de teclado: Enter termina el turno cuando es el mío y no hay
  // un input con foco (drawer, modales, etc.). Atajo solicitado en la
  // auditoría UX.
>>>>>>> main
  useEffect(() => {
    if (!mine) return
    const onKey = (e) => {
      if (e.key !== 'Enter') return
      const ae = document.activeElement
      if (ae && (ae.tagName === 'INPUT' || ae.tagName === 'TEXTAREA' || ae.isContentEditable)) return
      if (busy) return
      e.preventDefault()
      end()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [mine, busy, end])

  if (!mine) return null
  return (
    <button
      onClick={end} disabled={busy}
      title="Termina tu turno (Enter)"
      className="px-6 py-2.5 rounded-full bg-white text-black font-bold text-[11px] uppercase tracking-nike-wide
                 hover:bg-neon-lime transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed
                 flex items-center gap-2"
    >
      {busy ? '...' : (<>Terminar turno <span aria-hidden="true">↵</span></>)}
    </button>
  )
}

// Vive junto a EndTurnButton en el HUD del mapa — cuando NO es mi turno,
// este botón encadena llamadas a /simulate_bots/run en modo "step" (un bot
// por llamada, pausa de 4.5 s) hasta que vuelve mi turno. Así se ve:
//  - El TurnBanner cambiando: "Turno de Sur" → "Turno de Este" → "Turno de Oeste"
//  - El mapa repintándose entre bot y bot gracias al onRefresh
<<<<<<< Front_Ricardo
// Bot action overlay — animated cards, auto-dismiss 4.5 s, max 4 simultaneous
=======
// ─────────────────────────────────────────────────────────────
// Bot action overlay — animated cards for attack / conquer / fortify
// ─────────────────────────────────────────────────────────────
>>>>>>> main
const META_ACTION = {
  attack:  { emoji: '⚔️', label: 'ATACA',    glow: '#f43f5e' },
  conquer: { emoji: '🏴', label: 'CONQUISTA', glow: '#facc15' },
  fortify: { emoji: '🛡️', label: 'FORTIFICA', glow: '#06b6d4' },
}

<<<<<<< Front_Ricardo
function useReducedMotionCached() {
  const [reduced, setReduced] = useState(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return false
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches
  })
  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
    const handler = (e) => setReduced(e.matches)
    try { mq.addEventListener('change', handler) }
    catch { mq.addListener(handler) }
    return () => {
      try { mq.removeEventListener('change', handler) }
      catch { mq.removeListener(handler) }
    }
  }, [])
  return reduced
}

=======
/**
 * Overlay de acciones de bot.
 *
 * Cambios vs la versión anterior:
 *  - Cola propia con auto-dismiss (4.5 s por tarjeta). Antes las tarjetas
 *    se quedaban pegadas hasta que llegaba otro setBattleEvents y se
 *    solapaban con el TroopsReadout.
 *  - Máximo 4 tarjetas visibles — si llegan más se evaporan las más
 *    antiguas (FIFO). Evita que un bot con 15 acciones haga scroll infinito.
 *  - Posición movida a `right-4 bottom-28`: deja libre el flanco izquierdo
 *    (SimulateBotsButton banner) y no pisa TroopsReadout (center bottom).
 *  - Acepta `mapActionsRef` para que, al aparecer cada evento, la cámara
 *    vuele a la zona afectada y la zona pulse con el color del bot. Así el
 *    jugador VE dónde pasa la cosa en lugar de sólo leer tarjetas.
 *  - Cada evento muestra mini-contador de tiempo restante (barra inferior)
 *    para que el feedback de "se va a ir" sea obvio.
 *  - Se respeta prefers-reduced-motion: sin spring, sin pulso, transición simple.
 */
>>>>>>> main
const BattleEventOverlay = React.memo(BattleEventOverlayImpl)
function BattleEventOverlayImpl({ events, mapActionsRef, myUserId }) {
  const [queue, setQueue] = useState([])
  const seenRef = useRef(new Set())
  const reduceMotion = useReducedMotionCached()

<<<<<<< Front_Ricardo
=======
  // Ingresa eventos nuevos en la cola, aplicando fly-to + pulse en el mapa.
>>>>>>> main
  useEffect(() => {
    if (!events || events.length === 0) return
    const fresh = events.filter(ev => ev._key && !seenRef.current.has(ev._key))
    if (fresh.length === 0) return
    fresh.forEach(ev => seenRef.current.add(ev._key))
<<<<<<< Front_Ricardo
    setQueue(q => [...q, ...fresh].slice(-4))
=======
    setQueue(q => {
      const combined = [...q, ...fresh]
      return combined.slice(-4) // máximo 4 tarjetas simultáneas
    })
    // Encadenamos fly-to con 250 ms de offset entre acciones para que no
    // la cámara no brinque como una mosca. Sólo volamos para acciones que
    // tienen zone_id (idle ya viene filtrado por el caller).
>>>>>>> main
    const actions = mapActionsRef?.current
    if (!actions) return
    fresh.forEach((ev, i) => {
      const zoneId = ev.zone_id
      if (!zoneId) return
      const color = PLAYERS[ev.bot]?.color || '#ffffff'
      setTimeout(() => {
        try {
          actions.flyToZone?.(zoneId, { zoom: 14.2, duration: 750 })
          actions.pulseZone?.(zoneId, { color, duration: 2200 })
        } catch {}
      }, i * 250)
    })
  }, [events, mapActionsRef])

<<<<<<< Front_Ricardo
=======
  // Auto-dismiss: cada tarjeta vive 4.5 s desde que entra en cola.
>>>>>>> main
  useEffect(() => {
    if (queue.length === 0) return
    const oldest = queue[0]
    const t = setTimeout(() => {
      setQueue(q => q.filter(ev => ev._key !== oldest._key))
    }, 4500)
    return () => clearTimeout(t)
  }, [queue])

<<<<<<< Front_Ricardo
=======
  // Limpieza de `seenRef` cuando no hay nada en cola para que no crezca sin
  // fin durante una partida larga.
>>>>>>> main
  useEffect(() => {
    if (queue.length === 0) seenRef.current = new Set()
  }, [queue])

  if (queue.length === 0) return null
  return (
    <div
      className="absolute right-4 bottom-28 z-30 flex flex-col gap-2 max-w-[280px] pointer-events-none"
      role="status" aria-live="polite" aria-label="Acciones de los bots"
    >
      <AnimatePresence initial={false}>
        {queue.map((ev) => {
          const m = META_ACTION[ev.action] || { emoji: '•', label: String(ev.action || '').toUpperCase(), glow: '#fff' }
          const botColor = PLAYERS[ev.bot]?.color || '#fff'
<<<<<<< Front_Ricardo
=======
          // Si el bot ataca/conquista una zona MÍA, destacamos con emoji
          // de aviso para que el jugador lo registre al vuelo.
>>>>>>> main
          const attacksMe = ev.owner_user_id === myUserId && (ev.action === 'attack' || ev.action === 'conquer')
          return (
            <motion.div
              key={ev._key}
              layout
              initial={reduceMotion ? { opacity: 0 } : { opacity: 0, x: 40, scale: 0.9 }}
              animate={reduceMotion ? { opacity: 1 } : { opacity: 1, x: 0, scale: 1 }}
              exit={reduceMotion ? { opacity: 0 } : { opacity: 0, x: 40, scale: 0.9 }}
              transition={reduceMotion ? { duration: 0.15 } : { type: 'spring', damping: 22, stiffness: 260 }}
              className="relative rounded-2xl px-3 py-2.5 backdrop-blur-xl border overflow-hidden"
              style={{
                background: `${m.glow}14`,
                borderColor: attacksMe ? `${m.glow}cc` : `${m.glow}50`,
                boxShadow: attacksMe ? `0 0 26px ${m.glow}55` : `0 0 18px ${m.glow}22`,
              }}
            >
              <div className="flex items-center gap-1.5 mb-1">
                <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: botColor, boxShadow: `0 0 6px ${botColor}` }} />
                <span className="font-bold text-[10px] uppercase tracking-widest truncate" style={{ color: botColor }}>
                  {ev.botName}
                </span>
                <span className="ml-auto text-[10px] font-black px-1.5 py-0.5 rounded-full"
                  style={{ background: `${m.glow}22`, color: m.glow }}>
                  {m.emoji} {m.label}
                </span>
              </div>
              {ev.action === 'attack' && (
                <div className="text-[11px] leading-snug">
                  {ev.from_zone_name && <span className="text-white/55">{ev.from_zone_name} </span>}
                  <span className="text-white/35">→ </span>
                  <span className="font-bold" style={{ color: m.glow }}>{ev.zone_name}</span>
                  {attacksMe && <span className="ml-1 text-[9px] font-black text-white bg-rose-600/90 px-1.5 py-0.5 rounded-full">¡TE ATACA!</span>}
                </div>
              )}
              {ev.action === 'conquer' && (
                <div className="text-[11px] font-bold" style={{ color: m.glow }}>
                  {ev.zone_name}
                  {attacksMe && <span className="ml-1 text-[9px] font-black text-white bg-rose-600/90 px-1.5 py-0.5 rounded-full">¡TE LA QUITA!</span>}
                </div>
              )}
              {ev.action === 'fortify' && (
                <div className="text-[11px]">
                  <span className="text-white/55">{ev.zone_name}</span>
                  {ev.prev_defense != null && ev.new_defense != null && (
                    <span className="text-white/35"> {ev.prev_defense}→{ev.new_defense}</span>
                  )}
                </div>
              )}
              {/* Barra de vida de la tarjeta — 4.5 s fading */}
              <motion.div
                initial={{ scaleX: 1 }}
                animate={{ scaleX: 0 }}
                transition={{ duration: 4.5, ease: 'linear' }}
                className="absolute left-0 bottom-0 h-[2px] origin-left"
                style={{ background: m.glow, width: '100%', opacity: 0.55 }}
              />
            </motion.div>
          )
        })}
      </AnimatePresence>
    </div>
  )
}

<<<<<<< Front_Ricardo
=======
// Helper local que respeta prefers-reduced-motion. No añadimos una lib
// adicional — el CSS media query basta. Se memoiza con un único listener.
function useReducedMotionCached() {
  const [reduced, setReduced] = useState(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return false
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches
  })
  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
    const handler = (e) => setReduced(e.matches)
    try { mq.addEventListener('change', handler) }
    catch { mq.addListener(handler) } // Safari antiguos
    return () => {
      try { mq.removeEventListener('change', handler) }
      catch { mq.removeListener(handler) }
    }
  }, [])
  return reduced
}

>>>>>>> main
//  - Resumen de lo que hizo el bot (qué conquistó / atacó / fortificó)
// En total ~14 s para los 3 bots — Fran dijo "hazlos más lentos para
// percatarme" así que cadencia cómoda > velocidad.
function SimulateBotsButton({ myUserId, onRefresh, onBattleEvents }) {
  const turn = useTurnPoll()
  const [playing, setPlaying] = useState(false)
  const [step, setStep] = useState(0)
  const [currentBot, setCurrentBot] = useState('')
  const [lastSummary, setLastSummary] = useState(null)
<<<<<<< Front_Ricardo
=======

>>>>>>> main
  const isMyTurn = turn && turn.current_player_id === myUserId

  const run = useCallback(async () => {
    if (playing) return
    setPlaying(true); setStep(0); setLastSummary(null)
    const sleep = (ms) => new Promise(r => setTimeout(r, ms))
    try {
      for (let i = 0; i < 5; i++) {
        const tRes = await api.get('/api/v1/turn/')
        const curr = tRes.data
        if (curr?.current_player_id === myUserId) break
<<<<<<< Front_Ricardo
        const botName = PLAYERS[curr.current_player_id]?.name || 'bot'
        setCurrentBot(botName)
        setStep(i + 1)
        const simRes = await api.post('/api/v1/simulate_bots/run', { mode: 'step', actions_per_bot_turn: 15 })
        const played = simRes?.data?.turns_played?.[0]
        // Emit overlay events BEFORE refresh so map state is updated after
        if (played?.actions) {
          const evs = played.actions
            .filter(a => a.action !== 'idle')
            .map((a, idx) => ({ ...a, botName, bot: played.bot, _key: `${Date.now()}-${idx}` }))
          if (evs.length > 0) onBattleEvents?.(evs)
        }
        await onRefresh?.()
=======
        const botId = curr.current_player_id
        const botName = botId === 'demo-player-001' ? getNorteName() : (PLAYERS[botId]?.name || 'bot')
        setCurrentBot(botName)
        setStep(i + 1)
        const simRes = await api.post('/api/v1/simulate_bots/run', { mode: 'step', actions_per_bot_turn: 15 })
        // Emit overlay events PRIMERO — así la cámara vuela a la zona antes
        // de que llegue el refreshData y repinte todo. Así vemos la
        // acción "suceder".
        const played = simRes?.data?.turns_played?.[0]
        if (played?.actions) {
          const evs = played.actions
            .filter(a => a.action !== 'idle')
            .map((a, idx) => ({
              ...a, botName, bot: played.bot,
              _key: `${Date.now()}-${i}-${idx}`,
            }))
          if (evs.length > 0) onBattleEvents?.(evs)
        }
>>>>>>> main
        if (played?.summary) {
          const s = played.summary
          const parts = []
          if (s.conquer) parts.push(`${s.conquer} conq.`)
          if (s.attack)  parts.push(`${s.attack} ataq.`)
          if (s.fortify) parts.push(`${s.fortify} fort.`)
          setLastSummary({ bot: botName, text: parts.join(' · ') || 'sin acciones' })
        }
<<<<<<< Front_Ricardo
        const actionCount = played?.actions?.filter(a => a.action !== 'idle').length ?? 0
        const botDuration = Math.max(3000, Math.min(8000, 3000 + actionCount * 400))
=======
        // Damos tiempo al overlay para que termine las animaciones:
        // ~250 ms por acción + 1.5 s de colchón. Con eso la cámara
        // recorre toda la partida del bot sin sentirse atropellada.
        const acts = (played?.actions || []).filter(a => a.action !== 'idle').length
        const botDuration = Math.min(8000, Math.max(3500, acts * 550 + 1500))
        await onRefresh?.()
>>>>>>> main
        await sleep(botDuration)
      }
    } catch (e) {
      if (import.meta.env.DEV) console.warn('[simulate bots]', e?.message || e)
    } finally {
      setPlaying(false); setStep(0); setCurrentBot(''); setLastSummary(null)
      try { await onRefresh?.() } catch { /* ignore */ }
    }
  }, [playing, myUserId, onRefresh, onBattleEvents])

  const runRef = useRef(run)
  runRef.current = run
  const playingRef = useRef(playing)
  playingRef.current = playing

  const prevIsMyTurnRef = useRef(null)
  useEffect(() => {
    const prev = prevIsMyTurnRef.current
    prevIsMyTurnRef.current = isMyTurn
    if (prev !== true || isMyTurn !== false) return
    if (playingRef.current) return
    const t = setTimeout(() => runRef.current(), 1200)
    return () => clearTimeout(t)
  }, [isMyTurn])

  if (!turn) return null
<<<<<<< Front_Ricardo
  if (isMyTurn && !playing) return null
  const disabled = playing
=======
  const disabled = playing || isMyTurn
>>>>>>> main
  const showSummary = lastSummary && lastSummary.bot === currentBot
  // Cuando es mi turno el bot-button es puro ruido (Terminar Turno ya vive al
  // lado). Solo aparece mientras corren los bots o si el jugador tarda tanto
  // que prefiere re-lanzarlos a mano — en ese estado damos el copy corto.
  if (isMyTurn && !playing) return null
  const label = playing
    ? (showSummary
        ? `✓ ${currentBot}: ${lastSummary.text} (${step}/3)`
        : `Jugando ${currentBot}… (${step}/3)`)
    : '🤖 Jugar turnos de bots'
  return (
    <button
      type="button"
      onClick={run}
      disabled={disabled}
      title="Los bots juegan uno a uno hasta que vuelva tu turno."
      className="px-4 py-2.5 rounded-full font-bold text-[11px] uppercase tracking-nike-wide
                 transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed
                 flex items-center gap-2 border max-w-[420px] truncate"
      style={{
        background: disabled ? 'rgba(200,255,0,0.06)' : 'rgba(200,255,0,0.16)',
        borderColor: 'rgba(200,255,0,0.45)',
        color: '#c8ff00',
        boxShadow: disabled ? 'none' : '0 0 14px rgba(200,255,0,0.25)',
      }}
    >
      {label}
    </button>
  )
}

function EnvironmentBanner() {
  const [data, setData] = useState({ air: 1, weather: 1, combined: 1 })

  useEffect(() => {
    let alive = true
    const fetchOnce = async () => {
      try {
        const r = await api.get('/api/v1/multipliers/')
        if (alive) setData(r.data)
      } catch { /* ingestor not running yet — keep neutral */ }
    }
    fetchOnce()
    const id = setInterval(fetchOnce, 5000)
    return () => { alive = false; clearInterval(id) }
  }, [])

  // Color: green (>=1.2 boost), white (neutral), red (<=0.8 penalty)
  const tone =
    data.combined >= 1.2 ? '#facc15' :
    data.combined <= 0.8 ? '#f43f5e' : '#ffffff'

  return (
    <div
      title={`Aire ×${data.air}  ·  Clima ×${data.weather}`}
      className="px-4 py-2.5 rounded-full backdrop-blur-xl border bg-black/70 flex items-center gap-2 font-bold text-sm"
      style={{ borderColor: `${tone}55`, color: tone }}
    >
      <span className="text-xs opacity-70">×</span>
      <span style={{ textShadow: `0 0 8px ${tone}` }}>{data.combined.toFixed(2)}</span>
      <span className="text-xs opacity-70">aire/clima</span>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────
// MAP VIEW with real GeoJSON — Phase 2 redesign
// ─────────────────────────────────────────────────────────────
function MapView({ onBack, currentClanId, currentUserId, refreshData, zones = [], battles = [], battleHistory = [], wsStatus = 'idle', sendWs }) {
  // `user` se usa para leer el balance (power_points) sin tener que pasarlo
  // como prop. AuthContext es el source of truth y se mantiene fresco por
  // refreshData en el padre.
  const { user } = useAuth()
  const [selected, setSelected] = useState(null)
  const [actionPanel, setActionPanel] = useState(null)
  const [showHistory, setShowHistory] = useState(false)
  const [battleEvents, setBattleEvents] = useState([])
  const [mapRefreshKey, setMapRefreshKey] = useState(0)
  const [runMode, setRunMode] = useState(false)
  const [viewMode, setViewMode] = useState('control') // 'control' | 'pressure' | 'economy'
  const [conquering, setConquering] = useState(false)
  const [runSteps, setRunSteps] = useState(0)          // steps accumulated this run session
  const geoWatchRef = useRef(null)
  const lastPosRef = useRef(null)
  const stepSyncTimerRef = useRef(null)
  // Acciones imperativas expuestas por NeonMap (p. ej. "centrar en mis zonas").
  // NeonMap rellena este ref en su efecto de init.
  const mapActionsRef = useRef(null)

<<<<<<< Front_Ricardo
  const [adjacencyMap, setAdjacencyMap] = useState(null)
  const turn = useTurnPoll()

  // Contadores del mapa (86 zonas totales en v3)
=======
  // Contadores del mapa (84 zonas jugables — 86 del geojson menos les Cases
  // de Bàrcena y Mauella, que eran aisladas sin adyacencia):
  //   myZones    = las que posee este jugador (15 al empezar)
  //   enemyZones = las que poseen los otros 3 jugadores (45 al empezar)
  //   freeZones  = zonas sin dueño (26 libres para reclamar)
>>>>>>> main
  const myZones = zones.filter(z => z.owner_clan_id === currentUserId).length
  const conqueredZones = zones.filter(z => z.owner_clan_id).length
  const enemyZones = conqueredZones - myZones
  const freeZones = zones.filter(z => !z.owner_clan_id).length

<<<<<<< Front_Ricardo
  const myColor = PLAYERS[currentUserId]?.color || '#facc15'

  const myZoneIds = React.useMemo(
    () => new Set(zones.filter(z => z.owner_clan_id === currentUserId).map(z => z.id)),
    [zones, currentUserId],
  )

  const selectedIsConquistable = React.useMemo(() => {
    if (!selected || !adjacencyMap) return false
    const adj = adjacencyMap[selected.id] ?? []
    return adj.some(id => myZoneIds.has(id))
  }, [selected, adjacencyMap, myZoneIds])

  // Load adjacency map once on mount
  useEffect(() => {
    api.get('/api/v1/zones/adjacency').then(r => setAdjacencyMap(r.data)).catch(() => {})
  }, [])

  // Bump mapRefreshKey when zones prop changes (parent re-fetched)
  const prevZonesRef = useRef(zones)
  useEffect(() => {
    if (prevZonesRef.current !== zones) {
      prevZonesRef.current = zones
      setMapRefreshKey(k => k + 1)
    }
  }, [zones])

  // Re-sync selected zone data when zones refreshes
  useEffect(() => {
    if (!selected) return
    const fresh = zones.find(z => z.id === selected.id)
    if (fresh) setSelected(fresh)
  }, [zones]) // eslint-disable-line react-hooks/exhaustive-deps

  // Keyboard shortcuts: Escape closes any open panel
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') {
        setActionPanel(null)
        setSelected(null)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  // Auto-recenter on turn return (isMyTurn goes false → true)
  const prevIsMyTurnRef = useRef(null)
  useEffect(() => {
    const isMyTurn = turn?.current_player_id === currentUserId
    if (prevIsMyTurnRef.current === false && isMyTurn === true) {
      mapActionsRef.current?.flyToMyZones?.()
    }
    prevIsMyTurnRef.current = isMyTurn
  }, [turn, currentUserId])
=======
  // Color del jugador actual — fuente única en PLAYERS (módulo).
  const myColor = PLAYERS[currentUserId]?.color || '#facc15'

  // Grafo de adyacencia — se carga una única vez al montar MapView. Lo usamos
  // para decidir si una zona libre puede ser conquistada por el jugador (sólo
  // aparece el botón "¡Conquistar zona!" si la zona es vecina de alguna mía).
  // Es inmutable a lo largo de la partida así que no hace falta refrescarlo.
  const [adjacencyMap, setAdjacencyMap] = useState(null)
  useEffect(() => {
    let alive = true
    api.get('/api/v1/zones/adjacency')
      .then(r => { if (alive) setAdjacencyMap(r.data?.adjacency || {}) })
      .catch(() => { /* sin adjacency el botón Conquistar simplemente no aparecerá — degradación segura */ })
    return () => { alive = false }
  }, [])

  // Set de zone_ids propios: utilidad para O(1) lookup en la regla de adyacencia.
  const myZoneIds = React.useMemo(() =>
    new Set(zones.filter(z =>
      z.owner_clan_id === currentUserId ||
      (currentClanId && z.owner_clan_id === currentClanId)
    ).map(z => z.id))
  , [zones, currentUserId, currentClanId])

  // ¿La zona seleccionada (si es libre) es adyacente a alguna zona mía?
  const selectedIsConquistable = React.useMemo(() => {
    if (!selected?.id || selected.owner_clan_id || !adjacencyMap) return false
    const neighbors = adjacencyMap[selected.id] || []
    return neighbors.some(nid => myZoneIds.has(nid))
  }, [selected?.id, selected?.owner_clan_id, adjacencyMap, myZoneIds])

  // BUG detectado en la auditoría: tras el turno de los bots el contador
  // "Tuyas" bajaba pero el mapa seguía pintando las zonas con el color del
  // dueño anterior. Causa: `refreshData()` refrescaba el array `zones` del
  // padre, pero el GeoJSON interno de NeonMap sólo se re-colorea cuando
  // `refreshKey` cambia. Bumpeamos el refreshKey cada vez que `zones`
  // cambia de referencia → el mapa siempre está sincronizado con el HUD.
  useEffect(() => {
    if (!zones || zones.length === 0) return
    setMapRefreshKey(k => k + 1)
  }, [zones])

  // Re-sincroniza la zona seleccionada con el estado fresco del servidor.
  // BUG detectado jugando: el drawer inferior guarda un snapshot al hacer
  // click y lo enseña sin refrescar. Tras desplegar 27 tropas el drawer
  // seguía diciendo "2 tropas" aunque el backend ya tenía 29. Este efecto
  // emparejá la `selected` con la última fila del array `zones` cada vez
  // que `zones` cambia.
  useEffect(() => {
    if (!selected?.id || !zones || zones.length === 0) return
    const fresh = zones.find(z => z.id === selected.id)
    if (!fresh) return
    const nextArmies = Number(fresh.total_armies ?? fresh.defense_level ?? 0)
    const nextOwner  = fresh.owner_clan_id || ''
    const isMine     = nextOwner && (nextOwner === currentUserId || nextOwner === currentClanId)
    // Sólo disparamos setState si algo relevante cambió (evita re-renders en bucle).
    if (
      nextArmies === selected.total_armies &&
      nextArmies === selected.defense_level &&
      nextOwner === selected.owner_clan_id &&
      !!isMine === !!selected.isMine
    ) return
    setSelected(s => s && ({
      ...s,
      total_armies: nextArmies,
      defense_level: nextArmies,
      owner_clan_id: nextOwner,
      owner_clan_name: fresh.owner_clan_name || s.owner_clan_name || '',
      isMine: !!isMine,
    }))
  }, [zones, selected?.id, currentUserId, currentClanId])
>>>>>>> main

  const handleSuccess = () => {
    setActionPanel(null)
    setMapRefreshKey(k => k + 1)
    refreshData?.()
  }

  // Atajos de teclado: Esc cierra el drawer/ActionPanel/historial. Solicitado
  // en la auditoría UX: el mapa es táctil-first pero en escritorio esperas
  // poder salir de un panel sin ir a buscar la X.
  useEffect(() => {
    const onKey = (e) => {
      if (e.key !== 'Escape') return
      if (actionPanel) setActionPanel(null)
      else if (selected) setSelected(null)
      else if (showHistory) setShowHistory(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [actionPanel, selected, showHistory])

  // Auto-recentrar el mapa en mis zonas cuando vuelve mi turno. Detectado en
  // la auditoría: tras el ciclo de bots la cámara se quedaba pegada en la
  // última zona que atacó el bot (p. ej. Malilla) y el jugador perdía
  // contexto sobre dónde está jugando. En cuanto se detecta la transición
  // "no era mi turno → ahora sí", volamos a mi bounding box.
  const turnForMap = useTurnPoll()
  const prevWasMineRef = useRef(null)
  useEffect(() => {
    const mine = !!turnForMap && turnForMap.current_player_id === currentUserId
    const wasMine = prevWasMineRef.current
    prevWasMineRef.current = mine
    // Solo al transicionar false → true, y nunca al montar (prev=null).
    if (wasMine !== false || mine !== true) return
    // Pequeño retraso: el overlay de batalla acaba de soltar sus fly-to
    // escalonados; esperamos a que termine el último antes de recentrar.
    const t = setTimeout(() => {
      try { mapActionsRef.current?.centerOnMyZones?.() } catch {}
    }, 900)
    return () => clearTimeout(t)
  }, [turnForMap, currentUserId])

  const handleConquer = async () => {
    if (!selected) return
    setConquering(true)
    try {
      await api.post(`/api/v1/zones/${selected.id}/conquer`)
      setSelected(null)
      setMapRefreshKey(k => k + 1)
      refreshData?.()
    } catch (err) {
      alert(err.response?.data?.detail || 'No se pudo conquistar la zona')
    } finally {
      setConquering(false)
    }
  }

  // ── Run Mode: GPS tracking + step estimation + periodic sync ──
  useEffect(() => {
    if (!runMode) {
      // Stop GPS watch
      if (geoWatchRef.current != null) {
        navigator.geolocation.clearWatch(geoWatchRef.current)
        geoWatchRef.current = null
      }
      // Final step sync and reset
      if (stepSyncTimerRef.current) {
        clearInterval(stepSyncTimerRef.current)
        stepSyncTimerRef.current = null
      }
      setRunSteps(0)
      lastPosRef.current = null
      return
    }

    // Haversine distance in metres between two {lat,lng} coords
    const haversine = (a, b) => {
      const R = 6371000
      const dLat = (b.lat - a.lat) * Math.PI / 180
      const dLng = (b.lng - a.lng) * Math.PI / 180
      const sa = Math.sin(dLat / 2) ** 2 +
        Math.cos(a.lat * Math.PI / 180) * Math.cos(b.lat * Math.PI / 180) *
        Math.sin(dLng / 2) ** 2
      return R * 2 * Math.atan2(Math.sqrt(sa), Math.sqrt(1 - sa))
    }

    let sessionSteps = 0

    geoWatchRef.current = navigator.geolocation.watchPosition(
      (pos) => {
        const { latitude: lat, longitude: lng } = pos.coords
        // Send location to backend for zone detection + geofence
        sendWs?.({ event: 'location_update', lat, lng })

        // Estimate steps from distance (avg stride ~0.75 m)
        if (lastPosRef.current) {
          const dist = haversine(lastPosRef.current, { lat, lng })
          if (dist > 2) { // ignore GPS jitter < 2 m
            const newSteps = Math.round(dist / 0.75)
            sessionSteps += newSteps
            setRunSteps(s => s + newSteps)
          }
        }
        lastPosRef.current = { lat, lng }
      },
      () => {}, // silently ignore permission errors
      { enableHighAccuracy: true, maximumAge: 5000, timeout: 10000 },
    )

    // Sync accumulated steps to backend every 60 s
    stepSyncTimerRef.current = setInterval(async () => {
      if (sessionSteps <= 0) return
      const toSync = sessionSteps
      sessionSteps = 0
      try {
        await api.post('/api/v1/steps/sync', { steps: toSync })
        refreshData?.()
      } catch {}
    }, 60000)

    return () => {
      if (geoWatchRef.current != null) {
        navigator.geolocation.clearWatch(geoWatchRef.current)
        geoWatchRef.current = null
      }
      if (stepSyncTimerRef.current) {
        clearInterval(stepSyncTimerRef.current)
        stepSyncTimerRef.current = null
      }
    }
  }, [runMode, sendWs, refreshData])

  return (
    <motion.div
      key="map"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="absolute inset-0 overflow-hidden"
    >
      <div className={`absolute inset-0${runMode ? ' up-run-mode' : ''}`}>
        <NeonMap
          onZoneClick={setSelected}
          currentClanId={currentClanId}
          currentUserId={currentUserId}
          refreshKey={mapRefreshKey}
          viewMode={viewMode}
          battles={battles}
          actionsRef={mapActionsRef}
        />
        {/* Run Mode active border — neon lime frame */}
        {runMode && (
          <div className="absolute inset-0 pointer-events-none z-10"
            style={{ boxShadow: 'inset 0 0 0 3px #facc15, inset 0 0 60px rgba(202,255,51,0.10)' }} />
        )}
      </div>

      {/* Vignette */}
      <div className="absolute inset-0 pointer-events-none"
        style={{ background: 'radial-gradient(ellipse at center, transparent 50%, rgba(2,3,10,0.65) 100%)' }} />

      {/* ── TOP HUD ──
          flex-wrap: si la pantalla es estrecha los pills saltan a una
          segunda fila en lugar de salirse del viewport.
          pr-16 reserva espacio para el botón ⌖ "centrar en mis zonas". */}
      <div className="absolute top-0 left-0 right-0 z-20 px-5 pt-5 pr-16 flex items-center gap-3 flex-wrap">
        {/* Back */}
        <motion.button
          whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
          onClick={onBack}
          className="flex items-center gap-2 px-5 py-3 rounded-2xl backdrop-blur-xl border border-white/10 bg-black/70 text-white hover:border-neon-pink/50 transition font-bold text-lg">
          <ChevronLeft className="w-6 h-6" />
          Lobby
        </motion.button>

        {/* Run Mode toggle */}
        <motion.button
          whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
          animate={runMode ? {
            boxShadow: ['0 0 16px rgba(202,255,51,0.35)', '0 0 36px rgba(202,255,51,0.65)', '0 0 16px rgba(202,255,51,0.35)'],
          } : { boxShadow: '0 0 0px rgba(202,255,51,0)' }}
          transition={runMode ? { duration: 1.6, repeat: Infinity, ease: 'easeInOut' } : {}}
          onClick={() => setRunMode(r => !r)}
          className={`flex items-center gap-2 px-4 py-3 rounded-2xl backdrop-blur-xl border font-bold text-sm transition-colors ${
            runMode
              ? 'border-neon-lime/60 bg-neon-lime/15 text-neon-lime'
              : 'border-white/10 bg-black/70 text-white/50 hover:text-white/80'
          }`}
        >
          <Activity className="w-4 h-4" />
          {runMode ? 'RUN MODE' : 'Run'}
        </motion.button>

        {/* Run step counter — visible only while run mode is on */}
        {runMode && (
          <div className="px-3 py-2 rounded-xl backdrop-blur-xl border border-neon-lime/30 bg-black/70 flex items-center gap-1.5">
            <Footprints className="w-3.5 h-3.5 text-neon-lime" />
            <span className="text-xs font-bold text-neon-lime">{runSteps.toLocaleString()} pasos</span>
          </div>
        )}

        {/* Stats pills — Tuyas / Rivales / Libres.
            El color "Rivales" es naranja (#ff8c2a) — no coincide con
            ninguna facción (magenta Norte / lima Sur / cyan Este /
            púrpura Oeste) para no confundir al jugador.
            flex-wrap permite que salten de línea en pantallas estrechas. */}
        <div className="flex flex-wrap items-center gap-2 justify-center" role="status" aria-label="Estado del mapa">
          <div
            title={`Tienes ${myZones} zonas propias de 86 en el mapa`}
            aria-label={`Tus zonas: ${myZones}`}
            className="px-3 py-2 rounded-full backdrop-blur-xl border bg-black/70 flex items-center gap-2"
            style={{ borderColor: `${myColor}80` }}
          >
            <span
              className="w-2.5 h-2.5 rounded-full"
              style={{ background: myColor, boxShadow: `0 0 10px ${myColor}` }}
              aria-hidden="true"
            />
            <span className="text-[9px] uppercase tracking-widest font-bold opacity-70" style={{ color: myColor }}>Tuyas</span>
            <span className="text-base font-bold" style={{ color: myColor }}>{myZones}</span>
          </div>
          <div
            title={`${enemyZones} zonas de rivales · ${conqueredZones} ocupadas en total`}
            aria-label={`Zonas enemigas: ${enemyZones}`}
            className="px-3 py-2 rounded-full backdrop-blur-xl border bg-black/70 flex items-center gap-2"
            style={{ borderColor: 'rgba(255,140,42,0.45)' }}
          >
            <Swords className="w-4 h-4" style={{ color: '#ff8c2a' }} aria-hidden="true" />
            <span className="text-[9px] uppercase tracking-widest font-bold" style={{ color: 'rgba(255,140,42,0.75)' }}>Rivales</span>
            <span className="text-base font-bold" style={{ color: '#ff8c2a' }}>{enemyZones}</span>
          </div>
          <div
            title={`${freeZones} zonas sin dueño — reclámalas con "Desplegar"`}
            aria-label={`${freeZones} zonas libres`}
            className="px-3 py-2 rounded-full backdrop-blur-xl border border-white/15 bg-black/70 flex items-center gap-2"
          >
            <Target className="w-4 h-4 text-white/60" aria-hidden="true" />
            <span className="text-[9px] uppercase tracking-widest font-bold text-white/50">Libres</span>
            <span className="text-base font-bold text-white/80">{freeZones}</span>
          </div>
          {battles.length > 0 && (
            <div
              aria-label={`${battles.length} batallas activas`}
              className="px-5 py-2.5 rounded-full backdrop-blur-xl border border-neon-pink/40 bg-black/70 flex items-center gap-2.5"
            >
              <Swords className="w-4 h-4 text-neon-pink" aria-hidden="true" />
              <span className="text-base font-bold text-neon-pink">{battles.length} batallas</span>
            </div>
          )}
          <TurnBanner myUserId={currentUserId} />
          <EnvironmentBanner />
          <EndTurnButton myUserId={currentUserId} />
          <SimulateBotsButton myUserId={currentUserId} onRefresh={refreshData} onBattleEvents={setBattleEvents} />

          {/* Botón historial de batallas */}
          <motion.button
            whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
            onClick={() => setShowHistory(h => !h)}
            className={`flex items-center gap-2 px-4 py-3 rounded-2xl backdrop-blur-xl border font-bold text-sm transition-colors ${
              showHistory
                ? 'border-yellow-400/60 bg-yellow-400/15 text-yellow-300'
                : 'border-white/10 bg-black/70 text-white/60 hover:text-white/90'
            }`}
          >
            <ScrollText className="w-4 h-4" />
            Historial
            {battleHistory.length > 0 && (
              <span className="text-[10px] font-black px-1.5 py-0.5 rounded-full"
                style={{ background: 'rgba(200,255,0,0.2)', color: '#c8ff00' }}>
                {battleHistory.length}
              </span>
            )}
          </motion.button>
        </div>

        {/* Legend + WS indicator.
            hidden xl:flex oculta la leyenda en pantallas < 1280px (el HUD
            se queda con los pills esenciales). En desktop amplio se ven
            los 5 colores de facción. */}
        <div className="flex items-center gap-2">
          <WsIndicator status={wsStatus} />
          <div className="hidden xl:flex items-center gap-2">
            {[
              ['#f43f5e', 'Norte'],
              ['#facc15', 'Sur'],
              ['#06b6d4', 'Este'],
              ['#a855f7', 'Oeste'],
              ['#6b7280', 'Libre'],
            ].map(([color, label]) => (
              <div key={label} className="flex items-center gap-1.5 px-3 py-2 rounded-full bg-black/70 backdrop-blur-sm border border-white/10">
                <span className="w-2.5 h-2.5 rounded-full" style={{ background: color, boxShadow: `0 0 8px ${color}` }} />
                <span className="text-xs font-bold text-white/80">{label}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── ZONE BOTTOM DRAWER ── */}
      <AnimatePresence>
        {selected && !actionPanel && (
          <motion.div
            initial={{ y: '100%' }} animate={{ y: 0 }} exit={{ y: '100%' }}
            transition={{ type: 'spring', damping: 28, stiffness: 300 }}
            className="absolute bottom-0 left-0 right-0 z-20 rounded-t-3xl border-t border-white/10 overflow-hidden"
            style={{
              background: 'rgba(6,7,16,0.97)',
              backdropFilter: 'blur(28px)',
              boxShadow: `0 -24px 60px ${selected.color}25, 0 -4px 0 ${selected.color}40`,
            }}
          >
            {/* Handle */}
            <div className="flex justify-center pt-3 pb-1">
              <div className="w-10 h-1 rounded-full bg-white/20" />
            </div>

            {/* Zone info row */}
            <div className="px-6 pt-2 pb-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className="w-5 h-5 rounded-full flex-shrink-0"
                  style={{ background: selected.color, boxShadow: `0 0 14px ${selected.color}, 0 0 4px ${selected.color}` }} />
                <div>
                  <div className="text-[10px] uppercase tracking-widest font-bold text-white/40">Valencia · Distrito</div>
                  <h3 className="font-display font-extrabold text-white text-2xl leading-tight">{selected.name}</h3>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="text-right">
                  <div className="text-sm font-bold" style={{ color: selected.color }}>
                    {selected.owner_clan_id ? (selected.isMine ? '⚑ Tu territorio' : '⚔ Rival') : '◎ Libre'}
                  </div>
                  <div className="text-white/40 text-xs mt-0.5">{selected.total_armies} tropas</div>
                </div>
                <button onClick={() => setSelected(null)}
                  className="p-2 rounded-full hover:bg-white/10 text-white/40 hover:text-white transition">
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

<<<<<<< Front_Ricardo
            {/* Conquistar — shown only when zone is adjacent to an own zone */}
            {selectedIsConquistable && !selected.owner_clan_id && (
=======
            {/* Conquistar — sólo aparece para zonas libres que sean adyacentes
                a alguna zona propia. Cuesta 1 tropa: si no tienes disponibles
                el botón queda deshabilitado con un tooltip explicativo. */}
            {!selected.owner_clan_id && selectedIsConquistable && (() => {
              const canPay = (user?.power_points ?? 0) >= 1
              return (
                <div className="px-6 pb-4">
                  <motion.button
                    whileHover={canPay ? { scale: 1.02 } : {}}
                    whileTap={canPay ? { scale: 0.97 } : {}}
                    onClick={canPay ? handleConquer : undefined}
                    disabled={conquering || !canPay}
                    title={canPay
                      ? 'Reclama esta zona (cuesta 1 tropa de las disponibles)'
                      : 'Necesitas al menos 1 tropa disponible. Camina para ganarlas.'}
                    className="w-full py-4 rounded-2xl font-display font-extrabold text-lg flex items-center justify-center gap-3 border transition disabled:opacity-50 disabled:cursor-not-allowed"
                    style={{
                      background: conquering ? 'rgba(202,255,51,0.10)' : 'linear-gradient(135deg,rgba(202,255,51,0.25),rgba(202,255,51,0.10))',
                      borderColor: '#facc1560',
                      color: '#facc15',
                      boxShadow: conquering || !canPay ? 'none' : '0 0 24px rgba(202,255,51,0.20)',
                    }}>
                    <Crown className="w-5 h-5" />
                    {conquering
                      ? 'Conquistando…'
                      : canPay ? '¡Conquistar zona! (1 tropa)' : 'Sin tropas disponibles'}
                  </motion.button>
                </div>
              )
            })()}
            {!selected.owner_clan_id && !selectedIsConquistable && adjacencyMap && (
>>>>>>> main
              <div className="px-6 pb-4">
                <div className="px-4 py-3 rounded-xl border text-sm leading-snug"
                  style={{ background: 'rgba(255,255,255,0.04)', borderColor: 'rgba(255,255,255,0.10)', color: 'rgba(255,255,255,0.55)' }}>
                  Esta zona libre no es adyacente a ningún territorio tuyo. Conquista primero un barrio vecino para llegar.
                </div>
              </div>
            )}

            {/* Action buttons
                Reglas por zona:
                  - Mía       → Desplegar ✓, Atacar ✗, Fortificar ✓
                  - Rival     → Desplegar ✗, Atacar ✓, Fortificar ✗
                  - Libre     → Desplegar ✗, Atacar ✗, Fortificar ✗ (usa "¡Conquistar zona!")
                Desplegar sólo tiene sentido sobre territorio propio. */}
            <div className="px-6 pb-8 grid grid-cols-3 gap-3">
              {[
<<<<<<< Front_Ricardo
                { key: 'deploy',  label: 'Desplegar', Icon: Send,   color: '#facc15', bg: 'rgba(202,255,51,0.10)',  disabled: !selected.isMine },
                { key: 'attack',  label: 'Atacar',    Icon: Swords, color: '#f43f5e', bg: 'rgba(255,45,146,0.10)', disabled: selected.isMine || !selected.owner_clan_id },
                { key: 'fortify', label: 'Fortificar', Icon: Shield, color: '#06b6d4', bg: 'rgba(0,240,255,0.10)',  disabled: !selected.isMine },
              ].map(({ key, label, Icon, color, bg, disabled }) => (
=======
                { key: 'deploy',  label: 'Desplegar', Icon: Send,   color: '#facc15', bg: 'rgba(202,255,51,0.10)',
                  disabled: !selected.isMine,
                  tip: !selected.isMine
                    ? (selected.owner_clan_id ? 'Solo puedes desplegar en zonas propias' : 'Primero conquista esta zona libre')
                    : 'Envía tropas a esta zona' },
                { key: 'attack',  label: 'Atacar',    Icon: Swords, color: '#f43f5e', bg: 'rgba(255,45,146,0.10)',
                  disabled: selected.isMine || !selected.owner_clan_id,
                  tip: selected.isMine ? 'No puedes atacar tus propias zonas'
                     : !selected.owner_clan_id ? 'Zona libre — usa Conquistar' : 'Lanza una ofensiva' },
                { key: 'fortify', label: 'Fortificar', Icon: Shield, color: '#06b6d4', bg: 'rgba(0,240,255,0.10)',
                  disabled: !selected.isMine,
                  tip: !selected.isMine ? 'Solo puedes mover tropas desde zonas propias' : 'Mueve tropas a otro territorio tuyo' },
              ].map(({ key, label, Icon, color, bg, disabled, tip }) => (
>>>>>>> main
                <motion.button key={key}
                  whileHover={!disabled ? { scale: 1.04 } : {}}
                  whileTap={!disabled ? { scale: 0.96 } : {}}
                  onClick={() => !disabled && setActionPanel(key)}
                  disabled={disabled}
                  title={tip}
                  aria-label={`${label}: ${tip}`}
                  className="py-5 rounded-2xl flex flex-col items-center gap-2 border transition disabled:opacity-20 disabled:cursor-not-allowed"
                  style={{ background: bg, borderColor: disabled ? 'rgba(255,255,255,0.08)' : `${color}55`, color: disabled ? 'rgba(255,255,255,0.25)' : color,
                    boxShadow: disabled ? 'none' : `0 4px 20px ${color}22` }}>
                  <Icon className="w-6 h-6" />
                  <span className="font-display font-bold text-sm">{label}</span>
                </motion.button>
              ))}
            </div>
          </motion.div>
        )}

      </AnimatePresence>

      {/* ActionPanel rendered OUTSIDE the drawer AnimatePresence to avoid
          position:fixed being trapped by the parent's CSS transform context */}
      <AnimatePresence>
        {actionPanel && selected && (
          <ActionPanel
            key={actionPanel}
            kind={actionPanel}
            zone={selected}
            onClose={() => { setActionPanel(null); setMapRefreshKey(k => k + 1); refreshData?.() }}
            onSuccess={handleSuccess}
            onRefresh={() => { setMapRefreshKey(k => k + 1); refreshData?.() }}
          />
        )}
      </AnimatePresence>

      {/* Pill persistente: disponibles / en mapa / próx. bonus.
          Oculto si hay un zone drawer / ActionPanel abierto para no chocar. */}
      {!selected && !actionPanel && (
        <TroopsReadout zones={zones} currentUserId={currentUserId} myColor={myColor} />
      )}

      {/* Botón "Centrar en mis zonas" — React overlay posicionado fuera del
          HUD (right-4 top-24) para que nunca lo tape el HUD ni se pierda al
          hacer responsive. Llama a la acción imperativa que expone NeonMap. */}
      {/* ── Panel historial de batallas ── */}
      <AnimatePresence>
        {showHistory && (
          <motion.div
            key="history-panel"
            initial={{ opacity: 0, x: 40 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 40 }}
            transition={{ type: 'spring', stiffness: 320, damping: 32 }}
            className="absolute top-20 right-4 z-40 w-80 max-h-[70vh] flex flex-col rounded-2xl border overflow-hidden"
            style={{ background: 'rgba(6,7,16,0.92)', borderColor: 'rgba(200,255,0,0.2)', backdropFilter: 'blur(20px)' }}
          >
            {/* Header */}
            <div className="flex items-center gap-2 px-4 py-3 border-b" style={{ borderColor: 'rgba(200,255,0,0.15)' }}>
              <ScrollText className="w-4 h-4 flex-shrink-0" style={{ color: '#c8ff00' }} />
              <span className="font-display font-bold text-white text-xs uppercase tracking-widest flex-1">
                Historial de Batallas
              </span>
              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full mr-1"
                style={{ background: 'rgba(200,255,0,0.15)', color: '#c8ff00' }}>
                {battleHistory.length}
              </span>
              <button onClick={() => setShowHistory(false)}
                className="text-white/40 hover:text-white transition">
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Lista */}
            <div className="overflow-y-auto flex-1 px-3 py-3 space-y-2">
              {battleHistory.length === 0 ? (
                <div className="text-xs text-white/30 text-center py-6">Sin batallas registradas aún</div>
              ) : battleHistory.map(b => {
                const isAttacker = b.attacker_clan_id === currentUserId || b.attacker_clan_id === currentClanId
                const won = (isAttacker && b.result === 'attacker_wins') || (!isAttacker && b.result === 'defender_wins')
                const ongoing = b.result === 'ongoing'
                const label = ongoing ? '⚔ En curso' : won ? '✓ Victoria' : '✗ Derrota'
                const labelColor = won ? '#c8ff00' : ongoing ? '#c8ff00' : 'rgba(255,255,255,0.4)'
                const date = b.started_at
                  ? new Date(b.started_at).toLocaleString('es-ES', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
                  : ''
                return (
                  <div key={b.id}
                    className={`rounded-xl px-3 py-2.5 border transition ${!won && !ongoing ? 'opacity-55' : ''}`}
                    style={{ background: 'rgba(200,255,0,0.03)', borderColor: 'rgba(200,255,0,0.12)' }}>
                    <div className="flex items-center gap-2">
                      <span className="text-[9px] font-black uppercase tracking-widest flex-shrink-0"
                        style={{ color: labelColor }}>{label}</span>
                      <span className="flex-1 text-xs text-white truncate font-medium">
                        {b.zone_name || 'Zona desconocida'}
                      </span>
                      <span className="text-[9px] text-white/30 flex-shrink-0">{date}</span>
                    </div>
                    {b.attacker_rolls?.length > 0 && (
                      <div className="mt-1.5 flex items-center gap-2 text-[10px]">
                        <span className="text-white/50">Atk</span>
                        <span className="font-bold" style={{ color: '#c8ff00' }}>
                          [{b.attacker_rolls.join(', ')}]
                        </span>
                        <span className="text-white/30">vs</span>
                        <span className="text-white/50">Def</span>
                        <span className="font-bold text-white/70">
                          [{(b.defender_rolls || []).join(', ')}]
                        </span>
                        <span className="ml-auto text-[9px]" style={{ color: won ? '#c8ff00' : 'rgba(255,255,255,0.35)' }}>
                          {won ? `−${b.attacker_losses ?? 0} nuestros` : `−${b.attacker_losses ?? 0} nuestros`}
                        </span>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Bot action overlay ── */}
      <BattleEventOverlay events={battleEvents} mapActionsRef={mapActionsRef} myUserId={currentUserId} />

      <motion.button
        type="button"
        whileHover={{ scale: 1.08 }}
        whileTap={{ scale: 0.92 }}
        onClick={() => mapActionsRef.current?.centerOnMyZones?.()}
        className="absolute right-4 top-24 z-30 w-12 h-12 rounded-xl border backdrop-blur-xl flex items-center justify-center"
        style={{
          background: 'rgba(6,7,16,0.92)',
          borderColor: `${myColor}aa`,
          color: myColor,
          boxShadow: `0 6px 20px rgba(0,0,0,0.6), 0 0 16px ${myColor}33`,
        }}
        title="Centrar en mis zonas"
        aria-label="Centrar mapa en mis zonas"
      >
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="8"/>
          <circle cx="12" cy="12" r="2" fill="currentColor"/>
          <line x1="12" y1="2"  x2="12" y2="6"/>
          <line x1="12" y1="18" x2="12" y2="22"/>
          <line x1="2"  y1="12" x2="6"  y2="12"/>
          <line x1="18" y1="12" x2="22" y2="12"/>
        </svg>
      </motion.button>
    </motion.div>
  )
}

// ─────────────────────────────────────────────────────────────
// MAIN APP
// ─────────────────────────────────────────────────────────────
const TUTORIAL_KEY = 'cloudrisk_tutorial_done'
const DAILY_CLAIM_KEY = 'cloudrisk_daily_claim'
const todayStr = () => new Date().toISOString().split('T')[0]

// Tabla de premios diarios — weighted random
// El backend: power = steps // 100, gold = steps // 50
const DAILY_REWARDS = [
  { name: '⚡ Sprint Boost',    steps:   500, weight: 40 },  // 5 poder, 10 monedas
  { name: '👟 Corredor Urbano', steps:  1000, weight: 30 },  // 10 poder, 20 monedas
  { name: '🔥 Quema Asfalto',   steps:  2000, weight: 20 },  // 20 poder, 40 monedas
  { name: '💥 Poder Explosivo', steps:  5000, weight:  8 },  // 50 poder, 100 monedas
  { name: '👑 Leyenda Urbana',  steps: 10000, weight:  2 },  // 100 poder, 200 monedas
]
function pickDailyReward() {
  const total = DAILY_REWARDS.reduce((s, r) => s + r.weight, 0)
  let n = Math.random() * total
  for (const r of DAILY_REWARDS) { n -= r.weight; if (n <= 0) return r }
  return DAILY_REWARDS[0]
}

// Minimal inline toast host — non-intrusive, stacks, auto-dismiss
function ToastHost({ toasts }) {
  return (
    <div className="fixed top-4 right-4 z-[100] flex flex-col gap-2 pointer-events-none">
      <AnimatePresence>
        {toasts.map(t => (
          <motion.div
            key={t.id}
            initial={{ opacity: 0, x: 30 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 30 }}
            className="px-4 py-3 rounded-xl border backdrop-blur-xl text-sm font-bold max-w-xs"
            style={{
              background: 'rgba(8,10,20,0.9)',
              borderColor: t.level === 'error' ? '#f43f5e'
                         : t.level === 'success' ? '#facc15' : '#06b6d4',
              color: t.level === 'error' ? '#f43f5e'
                   : t.level === 'success' ? '#facc15' : '#06b6d4',
              boxShadow: `0 6px 24px ${t.level === 'error' ? '#f43f5e55' : '#06b6d433'}`,
            }}
          >
            {t.text}
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  )
}

export default function UrbanPacer() {
  const { user, setUser, logout, token } = useAuth()
  const [view, setView] = useState('lobby')
  const [claimed, setClaimed] = useState(() => {
    try {
      const s = JSON.parse(localStorage.getItem(DAILY_CLAIM_KEY) || 'null')
      return s?.date === todayStr() && s?.claimed === true
    } catch { return false }
  })
  const [showTutorial, setShowTutorial] = useState(
    () => !localStorage.getItem(TUTORIAL_KEY)
  )
  const [clans, setClans] = useState([])
  const [zones, setZones] = useState([])
  const [battles, setBattles] = useState([])
  const [missions, setMissions] = useState([])
  const [battleHistory, setBattleHistory] = useState([])
  const [leaderboard, setLeaderboard] = useState([])
  const [dataStatus, setDataStatus] = useState('idle') // 'idle'|'loading'|'ready'|'error'

  // ── Toast system ──
  const [toasts, setToasts] = useState([])
  const pushToast = useCallback((text, level = 'info', ttl = 3500) => {
    const id = Date.now() + Math.random()
    setToasts(ts => [...ts, { id, text, level }])
    setTimeout(() => setToasts(ts => ts.filter(t => t.id !== id)), ttl)
  }, [])

  // Debounced refresher for WS-triggered invalidations: durante la
  // simulación de bots el servidor emite hasta 15 eventos zone_updated
  // seguidos y antes cada uno disparaba 5 fetch en paralelo. Ahora los
  // colapsamos en una única llamada 800 ms después del último evento.
  const refreshDebounceRef = useRef(null)
  const requestRefresh = useCallback(() => {
    if (refreshDebounceRef.current) clearTimeout(refreshDebounceRef.current)
    refreshDebounceRef.current = setTimeout(() => {
      refreshDebounceRef.current = null
      refreshDataRef.current?.()
    }, 800)
  }, [])

  // refreshData declared early so WS handler can reference it
  const refreshDataRef = useRef(null)
  const refreshData = useCallback(async () => {
    if (!token) return
    setDataStatus(prev => (prev === 'ready' ? 'ready' : 'loading'))
    try {
      const [c, z, b, me, lb] = await Promise.all([
        api.get('/api/v1/clans/'),
        api.get('/api/v1/zones/'),
        api.get('/api/v1/battles/'),
        api.get('/api/v1/users/me'),
        api.get('/api/v1/users/leaderboard').catch(() => ({ data: [] })),
      ])
      // Silent refresh: only overwrite if we actually got data
      if (Array.isArray(c.data)) setClans(c.data)
      if (Array.isArray(z.data)) setZones(z.data)
      if (Array.isArray(b.data)) {
        setBattles(b.data.filter(x => x.result === 'ongoing'))
      }
      if (me.data) setUser(me.data)
      if (Array.isArray(lb.data)) setLeaderboard(lb.data)

      // Missions + battle history — en este juego clan_id es siempre null
      // (los 4 comandantes actúan como clan individual usando su propio id).
      // Por eso NO gateamos por clan_id; el backend ya filtra por el token.
      const [mRes, bhRes] = await Promise.all([
        api.get('/api/v1/missions/').catch(() => ({ data: [] })),
        api.get('/api/v1/battles/history').catch(() => ({ data: [] })),
      ])
      if (Array.isArray(mRes.data)) setMissions(mRes.data)
      if (Array.isArray(bhRes.data)) setBattleHistory(bhRes.data)
      setDataStatus('ready')
    } catch (e) {
      setDataStatus('error')
      pushToast('Sin conexión con el servidor', 'error')
    }
  }, [token, setUser, pushToast])
  useEffect(() => { refreshDataRef.current = refreshData }, [refreshData])

<<<<<<< Front_Ricardo
  // Debounced refresh: coalesces rapid WS events into one fetch
  const requestRefreshTimer = useRef(null)
  const requestRefresh = useCallback(() => {
    clearTimeout(requestRefreshTimer.current)
    requestRefreshTimer.current = setTimeout(() => refreshDataRef.current?.(), 800)
  }, [])

  // Refresca el historial de batallas cada 15 s (always when token exists)
=======
  // Refresca el historial de batallas cada 15 s sin relanzar el fetch completo.
  // BUG detectado en la auditoría: antes había un early-return si
  // `user?.clan_id` era falsy — pero en este juego los 4 comandantes NO
  // tienen clan asignado (clan_id siempre es null, el user.id actúa como
  // clan en toda la lógica de zonas). Ese guard hacía que el historial
  // NUNCA se poblase aunque el backend tuviera batallas. Ahora llamamos
  // siempre que haya token.
>>>>>>> main
  useEffect(() => {
    if (!token) return
    const poll = async () => {
      try {
        const r = await api.get('/api/v1/battles/history')
        if (Array.isArray(r.data)) setBattleHistory(r.data)
      } catch {}
    }
<<<<<<< Front_Ricardo
    poll()
=======
    poll() // primer fetch inmediato al montar
>>>>>>> main
    const id = setInterval(poll, 15000)
    return () => clearInterval(id)
  }, [token])

  // #1 — WebSocket cableado como invalidador del estado global
  const handleWsMessage = useCallback((msg) => {
    if (!msg?.event) return
    switch (msg.event) {
      case 'game_state_update':
      case 'zone_updated':
      case 'battle_started':
      case 'battle_resolved':
      case 'armies_placed':
      case 'armies_fortified':
        requestRefresh()
        break
      case 'location_ack': {
        const z = msg.zone
        if (z) {
          const zoneMsg = z.is_free
            ? `Zona libre: ${z.name} — ¡conquístala!`
            : `Entrando en ${z.name}`
          pushToast(zoneMsg, z.is_free ? 'success' : 'info')
        }
        break
      }
      case 'toast':
        pushToast(msg.text || 'Evento del servidor', msg.level || 'info')
        break
      default:
        // unhandled — silencio controlado
        break
    }
  }, [pushToast, requestRefresh])
  const { status: wsStatus, sendMessage: sendWs } = useWebSocket(user?.id, handleWsMessage)

  useEffect(() => {
    if (token) refreshData()
  }, [token, refreshData])

  // #2 — Al volver al lobby, resincronizar siempre
  useEffect(() => {
    if (view === 'lobby' && token) refreshData()
  }, [view, token, refreshData])

  const [claiming, setClaiming] = useState(false)

  const handleClaim = async () => {
    if (claimed || claiming) return null
    const reward = pickDailyReward()
    setClaiming(true)
    try {
      const r = await api.post('/api/v1/steps/sync', { steps: reward.steps })
      // Solo marcar como reclamado si el POST tuvo éxito
      setClaimed(true)
      localStorage.setItem(DAILY_CLAIM_KEY, JSON.stringify({ date: todayStr(), claimed: true }))
      await refreshData()
      const power = r?.data?.power_points_earned ?? r?.data?.power_earned
      const gold  = r?.data?.gold_earned
      return `${reward.name} · +${power ?? 0} poder  +${gold ?? 0} monedas`
    } catch (err) {
      pushToast(
        err.response?.data?.detail || 'No se pudo reclamar. Inténtalo de nuevo.',
        'error'
      )
      return null
    } finally {
      setClaiming(false)
    }
  }

  const handleTutorialClose = () => {
    localStorage.setItem(TUTORIAL_KEY, '1')
    setShowTutorial(false)
  }

  const handleReopenTutorial = () => {
    localStorage.removeItem(TUTORIAL_KEY)
    setShowTutorial(true)
  }

  const handleClaimMission = async (missionId) => {
    try {
      const r = await api.post(`/api/v1/missions/${missionId}/claim`)
      pushToast(`+${r.data.reward_power} poder  +${r.data.reward_gold} monedas`, 'success')
      // Refresh missions + user data
      const [mRes, me] = await Promise.all([
        api.get('/api/v1/missions/'),
        api.get('/api/v1/users/me'),
      ])
      if (Array.isArray(mRes.data)) setMissions(mRes.data)
      if (me.data) setUser(me.data)
    } catch (err) {
      pushToast(err.response?.data?.detail || 'No se pudo reclamar la misión', 'error')
    }
  }

  return (
    <div className="up-root fixed inset-0 overflow-hidden bg-ink-900 text-white">
      <AnimatePresence mode="wait">
        {!token ? (
          <LoginView key="login" wsStatus={wsStatus} player={user} />
        ) : view === 'lobby' ? (
          <Dashboard
            key="lobby"
            player={user || { name: '...', level: 1, power_points: 0, gold: 0, steps_total: 0 }}
            clans={clans}
            zones={zones}
            battles={battles}
            loading={dataStatus === 'loading' && clans.length === 0 && zones.length === 0}
            wsStatus={wsStatus}
            onStartRun={() => setView('map')}
            onClaim={handleClaim}
            claimed={claimed}
            claiming={claiming}
            onLogout={logout}
            onReopenTutorial={handleReopenTutorial}
            onRefresh={refreshData}
            missions={missions}
            battleHistory={battleHistory}
            leaderboard={leaderboard}
            onClaimMission={handleClaimMission}
          />
        ) : (
          <MapView
            key="map"
            currentClanId={user?.clan_id || null}
            currentUserId={user?.id || null}
            onBack={() => setView('lobby')}
            refreshData={refreshData}
            zones={zones}
            battles={battles}
            battleHistory={battleHistory}
            wsStatus={wsStatus}
            sendWs={sendWs}
          />
        )}
      </AnimatePresence>

      <AnimatePresence>
        {token && showTutorial && <Tutorial onClose={handleTutorialClose} />}
      </AnimatePresence>

      <ToastHost toasts={toasts} />
    </div>
  )
}
