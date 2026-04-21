import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { useEffect, useRef, useState } from 'react'
import api from '../api/client'

const ARMY_COLORS = ['#c41e3a', '#1e4d8c', '#2d5a27', '#c4a000', '#6b3fa0', '#d4740e']
const ZOOM_CLASSES = ['cq-zone-marker--hidden', 'cq-zone-marker--dot', 'cq-zone-marker--badge-only', 'cq-zone-marker--compact', 'cq-zone-marker--large']

function hashColor(seed) {
  let h = 0
  for (let i = 0; i < String(seed).length; i++) h = ((h << 5) - h + String(seed).charCodeAt(i)) | 0
  return ARMY_COLORS[Math.abs(h) % ARMY_COLORS.length]
}

function ringCoords(geom) {
  return geom.type === 'Polygon' ? geom.coordinates[0] : geom.coordinates[0][0]
}

function getCentroid(geom) {
  const coords = ringCoords(geom)
  let cx = 0, cy = 0
  coords.forEach(c => { cx += c[0]; cy += c[1] })
  return [cx / coords.length, cy / coords.length]
}

function distanceDeg(a, b) {
  return Math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)
}

const WATERCOLOR_STYLE = {
  version: 8,
  sources: {
    watercolor: {
      type: 'raster',
      tiles: ['https://tiles.stadiamaps.com/tiles/stamen_watercolor/{z}/{x}/{y}.jpg'],
      tileSize: 256,
      attribution: '&copy; <a href="https://stamen.com">Stamen</a> &middot; <a href="https://www.openstreetmap.org/copyright">OSM</a>',
    },
    labels: {
      type: 'raster',
      tiles: ['https://tiles.stadiamaps.com/tiles/stamen_toner_labels/{z}/{x}/{y}.png'],
      tileSize: 256,
    },
  },
  layers: [
    { id: 'watercolor', type: 'raster', source: 'watercolor' },
    { id: 'labels', type: 'raster', source: 'labels', paint: { 'raster-opacity': 0.35 } },
  ],
}

function buildPopupHTML(props) {
  const isOwned = !!props.ownerClanId
  const color = props.color || '#888'
  return `
    <div class="territory-card">
      <div class="territory-card-header" style="background:${color}">
        <span class="territory-icon">${isOwned ? '⚔️' : '🏳️'}</span>
        ${props.name || 'Desconocido'}
      </div>
      <div class="territory-card-body">
        <div class="territory-card-row">
          <span class="territory-card-label">Facción</span>
          <span class="territory-card-value">${props.ownerClanName || 'Tierra de Nadie'}</span>
        </div>
        <div class="territory-card-row">
          <span class="territory-card-label">Tropas</span>
          <span class="territory-card-value">${props.totalArmies || 0}</span>
        </div>
        <div class="territory-card-row">
          <span class="territory-card-label">Valor</span>
          <span class="territory-card-value">${props.value_score || props.population || '?'}</span>
        </div>
      </div>
    </div>
  `
}

function createConquestPulse(map, lngLat, color) {
  const id = 'cloudrisk-pulse-' + Date.now()
  map.addSource(id, {
    type: 'geojson',
    data: { type: 'Point', coordinates: [lngLat.lng, lngLat.lat] },
  })
  map.addLayer({
    id,
    type: 'circle',
    source: id,
    paint: {
      'circle-radius': 0,
      'circle-color': color,
      'circle-opacity': 0.6,
      'circle-stroke-width': 3,
      'circle-stroke-color': color,
      'circle-stroke-opacity': 0.8,
    },
  })

  let radius = 0
  let opacity = 0.6
  const animate = () => {
    radius += 2
    opacity -= 0.012
    if (opacity <= 0) {
      map.removeLayer(id)
      map.removeSource(id)
      return
    }
    map.setPaintProperty(id, 'circle-radius', radius)
    map.setPaintProperty(id, 'circle-opacity', opacity)
    map.setPaintProperty(id, 'circle-stroke-opacity', opacity)
    requestAnimationFrame(animate)
  }
  requestAnimationFrame(animate)
}

function NotificationToast({ notifications, onDismiss }) {
  if (!notifications.length) return null
  return (
    <div className="notif-stack">
      {notifications.map(n => (
        <div key={n.id} className={`notif-toast notif-toast--${n.type}`}>
          <span className="notif-icon">{n.icon}</span>
          <div className="notif-body">
            <div className="notif-title">{n.title}</div>
            <div className="notif-msg">{n.message}</div>
          </div>
          <button className="notif-close" onClick={() => onDismiss(n.id)}>✕</button>
        </div>
      ))}
    </div>
  )
}

function Minimap({ geojsonRef, playerPos }) {
  const miniRef = useRef(null)
  const miniMapRef = useRef(null)

  useEffect(() => {
    if (miniMapRef.current || !miniRef.current) return
    const mm = new maplibregl.Map({
      container: miniRef.current,
      style: {
        version: 8,
        sources: {
          osm: {
            type: 'raster',
            tiles: ['https://tiles.stadiamaps.com/tiles/stamen_watercolor/{z}/{x}/{y}.jpg'],
            tileSize: 256,
          },
        },
        layers: [{ id: 'base', type: 'raster', source: 'osm' }],
      },
      center: [-0.3900, 39.4650],
      zoom: 10,
      interactive: false,
      attributionControl: false,
    })
    miniMapRef.current = mm

    mm.on('load', () => {
      if (geojsonRef.current) {
        mm.addSource('zones-mini', { type: 'geojson', data: geojsonRef.current })
        mm.addLayer({
          id: 'zones-mini-fill', type: 'fill', source: 'zones-mini',
          paint: { 'fill-color': ['get', 'color'], 'fill-opacity': 0.6 },
        })
        mm.addLayer({
          id: 'zones-mini-border', type: 'line', source: 'zones-mini',
          paint: { 'line-color': 'rgba(44,24,16,0.5)', 'line-width': 0.5 },
        })
      }
    })

    return () => { mm.remove(); miniMapRef.current = null }
  }, [geojsonRef])

  useEffect(() => {
    const mm = miniMapRef.current
    if (!mm || !playerPos) return
    if (mm.getSource('player-mini')) {
      mm.getSource('player-mini').setData({
        type: 'Point', coordinates: [playerPos[1], playerPos[0]],
      })
    } else {
      mm.on('load', () => {
        if (mm.getSource('player-mini')) return
        mm.addSource('player-mini', {
          type: 'geojson',
          data: { type: 'Point', coordinates: [playerPos[1], playerPos[0]] },
        })
        mm.addLayer({
          id: 'player-mini-dot', type: 'circle', source: 'player-mini',
          paint: {
            'circle-radius': 5, 'circle-color': '#fff',
            'circle-stroke-width': 2, 'circle-stroke-color': '#c41e3a',
          },
        })
      })
    }
  }, [playerPos])

  return <div ref={miniRef} className="minimap" />
}

export default function GameMap({ onZoneClick, onLocationUpdate, selectedZone, viewMode = 'control', refreshKey }) {
  const containerRef = useRef(null)
  const mapRef = useRef(null)
  const markersRef = useRef([])
  const playerMarkerRef = useRef(null)
  const initRef = useRef(false)
  const hasCentered = useRef(false)
  const geojsonRef = useRef(null)
  const [playerPos, setPlayerPos] = useState(null)
  const [notifications, setNotifications] = useState([])

  const onZoneClickRef = useRef(onZoneClick)
  useEffect(() => { onZoneClickRef.current = onZoneClick }, [onZoneClick])
  const onLocationRef = useRef(onLocationUpdate)
  useEffect(() => { onLocationRef.current = onLocationUpdate }, [onLocationUpdate])

  const addNotification = (type, icon, title, message) => {
    const id = Date.now()
    setNotifications(prev => [...prev, { id, type, icon, title, message }])
    setTimeout(() => setNotifications(prev => prev.filter(n => n.id !== id)), 5000)
    if (Notification.permission === 'granted') {
      new Notification(title, { body: message, icon: '/favicon.ico' })
    }
  }

  const dismissNotification = (id) => {
    setNotifications(prev => prev.filter(n => n.id !== id))
  }

  useEffect(() => {
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission()
    }
  }, [])

  useEffect(() => {
    if (initRef.current) return
    initRef.current = true

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: WATERCOLOR_STYLE,
      center: [-0.3900, 39.4650],
      zoom: 12,
    })
    mapRef.current = map

    map.addControl(new maplibregl.NavigationControl(), 'top-right')
    map.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-right')

    map.on('load', async () => {
      let geojson = null
      for (const path of ['/valencia_districts.geojson', '/valencia_original_57.geojson']) {
        try {
          const res = await fetch(path)
          if (res.ok) { geojson = await res.json(); break }
        } catch { /* next */ }
      }

      let serverData = []
      try {
        const res = await api.get('/api/v1/state/locations')
        serverData = Array.isArray(res.data) ? res.data : []
      } catch {
        try {
          const res = await api.get('/api/v1/zones/')
          serverData = Array.isArray(res.data) ? res.data : []
        } catch { serverData = [] }
      }

      if (!geojson?.features?.length && serverData.length) {
        geojson = {
          type: 'FeatureCollection',
          features: serverData.filter(z => z.geojson).map((z, i) => ({
            type: 'Feature', id: i,
            properties: {
              name: z.name, id: z.id,
              color: hashColor(z.owner_clan_id || z.name),
              totalArmies: z.total_armies || z.defense_level || 0,
              ownerClanId: z.owner_clan_id || '',
              ownerClanName: z.owner_clan_name || '',
              value_score: z.value || 0,
            },
            geometry: z.geojson,
          })),
        }
      }

      if (!geojson?.features?.length) return

      const byName = new Map(serverData.map(l => [l.name?.toLowerCase(), l]))
      geojson.features.forEach((f, i) => {
        const match = byName.get(f.properties.name?.toLowerCase()) || {}
        const color = match.owner_clan_color || hashColor(match.owner_clan_id || match.dominant_user_id || f.properties.name)
        f.properties.color = color
        f.properties.totalArmies = match.total_armies || match.defense_level || f.properties.totalArmies || 0
        f.properties.ownerClanId = match.owner_clan_id || match.dominant_user_id || f.properties.ownerClanId || ''
        f.properties.ownerClanName = match.owner_clan_name || f.properties.ownerClanName || ''
        f.properties.value_score = match.value || match.value_score || f.properties.value_score || f.properties.population || 0
        if (f.id === undefined) f.id = i
      })

      geojsonRef.current = geojson

      const mapCenter = map.getCenter()
      const centerCoord = [mapCenter.lng, mapCenter.lat]
      geojson.features.forEach(f => {
        const centroid = getCentroid(f.geometry)
        const dist = distanceDeg(centroid, centerCoord)
        f.properties.fogOpacity = Math.max(0.15, Math.min(0.55, 0.55 - dist * 3))
      })

      map.addSource('zones', { type: 'geojson', data: geojson })

      map.addLayer({
        id: 'zones-fill', type: 'fill', source: 'zones',
        paint: {
          'fill-color': ['get', 'color'],
          'fill-opacity': ['case',
            ['boolean', ['feature-state', 'hover'], false], 0.75,
            ['get', 'fogOpacity']],
        },
      })

      map.addLayer({
        id: 'zones-border', type: 'line', source: 'zones',
        paint: {
          'line-color': ['case',
            ['boolean', ['feature-state', 'hover'], false], '#ffffff',
            'rgba(44,24,16,0.7)'],
          'line-width': ['case',
            ['boolean', ['feature-state', 'hover'], false], 2.5, 1.2],
          'line-dasharray': [4, 2],
        },
      })

      function zoomClass(z, areaDeg) {
        const large  = areaDeg > 0.0005
        const medium = areaDeg > 0.00008
        if (z < 11) return 'cq-zone-marker--hidden'
        if (z < 12) return large ? 'cq-zone-marker--dot' : 'cq-zone-marker--hidden'
        if (z < 13) return large ? 'cq-zone-marker--badge-only' : medium ? 'cq-zone-marker--dot' : 'cq-zone-marker--hidden'
        if (z < 14) return large ? 'cq-zone-marker--compact' : medium ? 'cq-zone-marker--badge-only' : 'cq-zone-marker--dot'
        if (z < 15) return large ? '' : medium ? 'cq-zone-marker--compact' : 'cq-zone-marker--badge-only'
        return large ? 'cq-zone-marker--large' : ''
      }

      function getBboxArea(geom) {
        const coords = ringCoords(geom)
        let minLng = Infinity, maxLng = -Infinity, minLat = Infinity, maxLat = -Infinity
        for (const c of coords) {
          if (c[0] < minLng) minLng = c[0]
          if (c[0] > maxLng) maxLng = c[0]
          if (c[1] < minLat) minLat = c[1]
          if (c[1] > maxLat) maxLat = c[1]
        }
        return (maxLng - minLng) * (maxLat - minLat)
      }

      const currentZoom = map.getZoom()
      geojson.features.forEach(f => {
        const { name, totalArmies, color, fogOpacity } = f.properties
        const area = getBboxArea(f.geometry)
        const el = document.createElement('div')
        const zc = zoomClass(currentZoom, area)
        el.className = `cq-zone-marker${zc ? ` ${zc}` : ''}`
        el.style.opacity = String(Math.max(0.3, fogOpacity / 0.55))
        el.innerHTML =
          `<div class="cq-zm-name">${name}</div>` +
          `<div class="cq-zm-badge" style="background:${color};box-shadow:0 0 10px ${color}88">${totalArmies || 0}</div>`
        markersRef.current.push({
          m: new maplibregl.Marker({ element: el, anchor: 'center' }).setLngLat(getCentroid(f.geometry)).addTo(map),
          area,
        })
      })

      function applyZoomClass(z) {
        markersRef.current.forEach(({ m, area }) => {
          const el = m.getElement()
          const newClass = zoomClass(z, area)
          const cur = ZOOM_CLASSES.find(c => el.classList.contains(c)) ?? ''
          if (cur === newClass) return
          ZOOM_CLASSES.forEach(c => el.classList.remove(c))
          if (newClass) el.classList.add(newClass)
        })
      }
      map.on('zoomend', () => applyZoomClass(map.getZoom()))

      map.on('moveend', () => {
        const c = map.getCenter()
        const cc = [c.lng, c.lat]
        const src = map.getSource('zones')
        if (!src || !geojsonRef.current) return
        geojsonRef.current.features.forEach(f => {
          const centroid = getCentroid(f.geometry)
          const dist = distanceDeg(centroid, cc)
          f.properties.fogOpacity = Math.max(0.15, Math.min(0.55, 0.55 - dist * 3))
        })
        src.setData(geojsonRef.current)
        markersRef.current.forEach(({ m }, i) => {
          const f = geojsonRef.current.features[i]
          if (f) m.getElement().style.opacity = String(Math.max(0.3, f.properties.fogOpacity / 0.55))
        })
      })

      let hoveredId = null
      map.on('mousemove', 'zones-fill', (e) => {
        if (!e.features?.length) return
        if (hoveredId !== null) map.setFeatureState({ source: 'zones', id: hoveredId }, { hover: false })
        hoveredId = e.features[0].id
        map.setFeatureState({ source: 'zones', id: hoveredId }, { hover: true })
        map.getCanvas().style.cursor = 'pointer'
      })
      map.on('mouseleave', 'zones-fill', () => {
        if (hoveredId !== null) { map.setFeatureState({ source: 'zones', id: hoveredId }, { hover: false }); hoveredId = null }
        map.getCanvas().style.cursor = ''
      })

      map.on('click', 'zones-fill', (e) => {
        if (!e.features?.length) return
        const p = e.features[0].properties

        createConquestPulse(map, e.lngLat, p.color || '#c41e3a')

        new maplibregl.Popup({ offset: 10, maxWidth: '280px' })
          .setLngLat(e.lngLat)
          .setHTML(buildPopupHTML(p))
          .addTo(map)

        if (p.ownerClanId) {
          addNotification('warning', '⚔️', 'Territorio Enemigo',
            `${p.name} controlado por ${p.ownerClanName || 'una facción enemiga'} con ${p.totalArmies || 0} tropas.`)
        } else {
          addNotification('info', '🏳️', 'Tierra de Nadie',
            `${p.name} está sin conquistar. ¡Despliega tropas para reclamarlo!`)
        }

        onZoneClickRef.current?.({
          id: p.id, name: p.name,
          total_armies: p.totalArmies || 0,
          defense_level: p.totalArmies || 0,
          owner_clan_id: p.ownerClanId || '',
          owner_clan_name: p.ownerClanName || '',
          owner_color: p.color || '',
          value: p.value_score || 0,
        })
      })
    })

    // Capturamos watchId para clearWatch en cleanup y evitar watchers duplicados
    let watchId = null
    if (navigator.geolocation) {
      watchId = navigator.geolocation.watchPosition(
        ({ coords: { latitude: lat, longitude: lng } }) => {
          setPlayerPos([lat, lng])

          if (!playerMarkerRef.current) {
            const el = document.createElement('div')
            el.innerHTML = `
              <svg width="28" height="36" viewBox="0 0 28 36">
                <line x1="4" y1="2" x2="4" y2="34" stroke="#2c1810" stroke-width="2.5" stroke-linecap="round"/>
                <polygon points="6,3 26,8 6,15" fill="#c41e3a" stroke="#8b1a1a" stroke-width="1"/>
                <circle cx="4" cy="34" r="2.5" fill="#2c1810"/>
              </svg>`
            el.style.cursor = 'pointer'
            playerMarkerRef.current = new maplibregl.Marker({ element: el, anchor: 'bottom' })
              .setLngLat([lng, lat]).addTo(map)
          } else {
            playerMarkerRef.current.setLngLat([lng, lat])
          }

          if (!hasCentered.current) {
            map.flyTo({ center: [lng, lat], zoom: 14, speed: 0.8 })
            hasCentered.current = true
          }
          onLocationRef.current?.(lat, lng)
        },
        () => {},
        { enableHighAccuracy: true, maximumAge: 5000 },
      )
    }

    return () => {
      if (watchId !== null && navigator.geolocation) {
        navigator.geolocation.clearWatch(watchId)
      }
      markersRef.current.forEach(({ m }) => m.remove())
      markersRef.current = []
      playerMarkerRef.current?.remove()
      playerMarkerRef.current = null
      map.remove()
      mapRef.current = null
      initRef.current = false
      hasCentered.current = false
    }
  }, [])

  return (
    <div className="map-wrapper">
      <NotificationToast notifications={notifications} onDismiss={dismissNotification} />
      <div ref={containerRef} className="map-container" />
    </div>
  )
}
