import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8080',
  timeout: 10000,
})

// C-1: clave sincronizada con AuthContext (usa 'cloudrisk_token')
const token = localStorage.getItem('cloudrisk_token')
if (token) {
  api.defaults.headers.common['Authorization'] = `Bearer ${token}`
}

// C-3: interceptor 401 — sesión expirada redirige al logout automáticamente
let _logoutHandler = null
export const setLogoutHandler = (fn) => { _logoutHandler = fn }

api.interceptors.response.use(
  r => r,
  err => {
    if (err.response?.status === 401) {
      _logoutHandler?.()
    }
    return Promise.reject(err)
  }
)

export default api
