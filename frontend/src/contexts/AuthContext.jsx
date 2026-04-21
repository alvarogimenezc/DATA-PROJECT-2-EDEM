import { createContext, useContext, useEffect, useState } from 'react'
import api from '../api/client'

const AuthContext = createContext(null)

// Lobby = 4 fixed seeded players (data/players.json on the backend).
// The human player defaults to Norte so a single person can play vs 3 bots
// without the auto-login putting them inside a bot. Override with
// ?player=sur|este|oeste in the URL to switch.
const LOBBY_PLAYERS = [
  { key: 'norte', email: 'norte@cloudrisk.app', password: 'demo1234' },
  { key: 'sur',   email: 'sur@cloudrisk.app',   password: 'demo1234' },
  { key: 'este',  email: 'este@cloudrisk.app',  password: 'demo1234' },
  { key: 'oeste', email: 'oeste@cloudrisk.app', password: 'demo1234' },
]

function pickLobbyPlayer() {
  const urlParams = new URLSearchParams(window.location.search)
  const wanted = (urlParams.get('player') || 'norte').toLowerCase()
  return LOBBY_PLAYERS.find((p) => p.key === wanted) || LOBBY_PLAYERS[0]
}

async function autoLoginAsLobbyPlayer() {
  const player = pickLobbyPlayer()
  const params = new URLSearchParams()
  params.append('username', player.email)
  params.append('password', player.password)
  const r = await api.post('/api/v1/users/login', params, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  })
  return { token: r.data.access_token, user: r.data.user }
}

// Module-level guard so React 18 StrictMode's double-effect doesn't double-register.
// We persist localStorage from inside the promise so the second mount sees a token
// and skips re-registering.
let bootstrapPromise = null

export function AuthProvider({ children }) {
  const [token, setToken] = useState(localStorage.getItem('cloudrisk_token'))
  const [user, setUser] = useState(null)
  const [bootstrapping, setBootstrapping] = useState(true)

  useEffect(() => {
    if (!bootstrapPromise) {
      bootstrapPromise = (async () => {
        const stored = localStorage.getItem('cloudrisk_token')
        if (stored) {
          api.defaults.headers.common['Authorization'] = `Bearer ${stored}`
          try {
            const r = await api.get('/api/v1/users/me')
            return { token: stored, user: r.data }
          } catch {
            localStorage.removeItem('cloudrisk_token')
            delete api.defaults.headers.common['Authorization']
          }
        }
        const fresh = await autoLoginAsLobbyPlayer()
        localStorage.setItem('cloudrisk_token', fresh.token)
        api.defaults.headers.common['Authorization'] = `Bearer ${fresh.token}`
        return fresh
      })()
    }

    let active = true
    bootstrapPromise
      .then(({ token: t, user: u }) => {
        if (!active) return
        setToken(t)
        setUser(u)
      })
      .catch(() => { /* auto-login failed, app renders without auth */ })
      .finally(() => { if (active) setBootstrapping(false) })
    return () => { active = false }
  }, [])

  const login = (accessToken, userData) => {
    localStorage.setItem('cloudrisk_token', accessToken)
    localStorage.removeItem('cloudrisk_tutorial_done')
    api.defaults.headers.common['Authorization'] = `Bearer ${accessToken}`
    setToken(accessToken)
    setUser(userData)
  }

  const logout = () => {
    localStorage.removeItem('cloudrisk_token')
    localStorage.removeItem('cloudrisk_tutorial_done')
    delete api.defaults.headers.common['Authorization']
    setToken(null)
    setUser(null)
    // After logout, the bootstrap effect re-runs only on full reload; trigger one
    // so the user lands back in the game instead of staring at a blank screen.
    window.location.reload()
  }

  return (
    <AuthContext.Provider value={{ token, user, setUser, login, logout, bootstrapping }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
