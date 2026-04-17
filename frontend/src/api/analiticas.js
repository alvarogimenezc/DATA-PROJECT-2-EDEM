import api from './client'

const BASE = '/api/v1/analytics'

export const getTopStepsMonth = (limit = 10) =>
  api.get(`${BASE}/top-steps-month`, { params: { limit } }).then(r => r.data)

export const getTopRainyDays = (limit = 10) =>
  api.get(`${BASE}/top-rainy-days`, { params: { limit } }).then(r => r.data)

export const getTopBadAir = (limit = 10) =>
  api.get(`${BASE}/top-bad-air`, { params: { limit } }).then(r => r.data)

export const getUserHistory = (playerId, days = 7) =>
  api.get(`${BASE}/user/${playerId}/history`, { params: { days } }).then(r => r.data)

export const getAntiCheatRejects = (limit = 50) =>
  api.get(`${BASE}/anti-cheat-rejects`, { params: { limit } }).then(r => r.data)
