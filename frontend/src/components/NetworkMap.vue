<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { LngLatBounds, Map as MapLibre, Marker, NavigationControl, setWorkerUrl } from 'maplibre-gl'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'
import zimbabwe from '../assets/zimbabwe.json'
import context from '../assets/midlands-context.json'
import { useConsole } from '../stores/console'
import { siteColor, siteSummary } from '../lib/power'
import { percent } from '../lib/format'

setWorkerUrl(workerUrl)

const BASEMAP = import.meta.env.VITE_BASEMAP_STYLE ?? 'https://tiles.openfreemap.org/styles/dark'
const OVERLAY_SOURCES = ['mask', 'zimbabwe', 'roads', 'routes', 'crews']
const RING = 13
const CIRCUMFERENCE = 2 * Math.PI * RING

const store = useConsole()
const container = ref(null)
const ready = ref(false)
let map
const markers = new Map()
const depotMarkers = new Map()
const townMarkers = []
let flewIn = false

const reducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches

const fallbackStyle = {
  version: 8,
  sources: {},
  layers: [{ id: 'background', type: 'background', paint: { 'background-color': '#0b1520' } }],
}

const mask = {
  type: 'Feature',
  geometry: {
    type: 'Polygon',
    coordinates: [[[-180, -85], [180, -85], [180, 85], [-180, 85], [-180, -85]], zimbabwe.geometry.coordinates[0]],
  },
}

const hasBasemap = () => Object.keys(map.getStyle()?.sources ?? {}).some((id) => !OVERLAY_SOURCES.includes(id))

function addOverlays() {
  if (!map.getSource('mask')) {
    map.addSource('mask', { type: 'geojson', data: mask })
    map.addSource('zimbabwe', { type: 'geojson', data: zimbabwe })
    map.addSource('roads', {
      type: 'geojson',
      data: {
        type: 'FeatureCollection',
        features: context.roads.map((coordinates) => ({ type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates } })),
      },
    })
    map.addSource('routes', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } })
    map.addSource('crews', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } })
  }
  const layers = [
    { id: 'zim-fill', type: 'fill', source: 'zimbabwe', paint: { 'fill-color': '#14273a', 'fill-opacity': hasBasemap() ? 0 : 1 } },
    {
      id: 'roads',
      type: 'line',
      source: 'roads',
      layout: { 'line-join': 'round', 'line-cap': 'round', visibility: hasBasemap() ? 'none' : 'visible' },
      paint: { 'line-color': '#2a4157', 'line-width': ['interpolate', ['linear'], ['zoom'], 6, 1, 10, 2.5] },
    },
    { id: 'mask', type: 'fill', source: 'mask', paint: { 'fill-color': '#09121c', 'fill-opacity': 0.72 } },
    { id: 'zim-line', type: 'line', source: 'zimbabwe', paint: { 'line-color': '#4a6178', 'line-width': 1.2 } },
    {
      id: 'routes',
      type: 'line',
      source: 'routes',
      layout: { 'line-cap': 'round' },
      paint: {
        'line-color': ['match', ['get', 'kind'], 'security', '#e5455a', '#c98012'],
        'line-width': 1.6,
        'line-opacity': 0.85,
        'line-dasharray': [1, 2.2],
      },
    },
    {
      id: 'crews',
      type: 'circle',
      source: 'crews',
      paint: {
        'circle-radius': 5,
        'circle-color': ['match', ['get', 'kind'], 'security', '#e5455a', '#c98012'],
        'circle-stroke-color': '#0e1926',
        'circle-stroke-width': 2,
      },
    },
  ]
  for (const layer of layers) if (!map.getLayer(layer.id)) map.addLayer(layer)
  syncTowns()
  updateRoutes()
}

function syncTowns() {
  const show = !hasBasemap()
  if (show && !townMarkers.length) {
    for (const town of context.towns) {
      const el = document.createElement('div')
      el.className = town.major ? 'town town--major' : 'town'
      el.textContent = town.name
      townMarkers.push(new Marker({ element: el, anchor: 'bottom', offset: [0, -22] }).setLngLat([town.lon, town.lat]).addTo(map))
    }
  } else if (!show) {
    townMarkers.splice(0).forEach((marker) => marker.remove())
  }
}

function glyph(site) {
  const color = siteColor(site)
  const up = site.status === 'up'
  const arc = up ? Math.max(0.04, Math.min(1, site.soc)) * CIRCUMFERENCE : 0
  const track = up ? '#243649' : color
  const trackOpacity = up ? 1 : 0.45
  let core
  if (site.status === 'dark') {
    core = `<circle cx="20" cy="20" r="5.5" fill="#0e1926" stroke="${color}" stroke-width="2"/>
            <path d="M16.5 23.5 23.5 16.5" stroke="${color}" stroke-width="2" stroke-linecap="round"/>`
  } else if (site.status === 'link_down') {
    core = `<path d="M15 20h3.2M21.8 20H25" stroke="${color}" stroke-width="2.4" stroke-linecap="round"/>`
  } else {
    core = `<circle cx="20" cy="20" r="${site.sleeping ? 3.5 : 5}" fill="${color}" opacity="${site.sleeping ? 0.55 : 1}"/>`
  }
  return `<svg viewBox="0 0 40 40" width="40" height="40" aria-hidden="true">
    <circle cx="20" cy="20" r="${RING}" fill="#0e1926" fill-opacity="0.82" stroke="${track}" stroke-opacity="${trackOpacity}" stroke-width="3"/>
    <circle cx="20" cy="20" r="${RING}" fill="none" stroke="${color}" stroke-width="3" stroke-linecap="round"
      stroke-dasharray="${arc.toFixed(2)} ${CIRCUMFERENCE.toFixed(2)}" transform="rotate(-90 20 20)"/>
    ${core}
  </svg>`
}

function signature(site) {
  return [site.status, site.power_source, Math.round(site.soc * 40), site.sleeping].join('|')
}

function syncMarkers() {
  if (!map) return
  const zone = store.highlightedZone
  const pendingSites = new Set(store.waiting.map((r) => r.site_id))
  let created = false
  for (const site of store.sites) {
    let entry = markers.get(site.id)
    if (!entry) {
      const el = document.createElement('button')
      el.type = 'button'
      el.className = 'site'
      el.innerHTML = `<span class="site__tether"></span><span class="site__glyph"></span><span class="site__badge"></span><span class="site__label"></span>`
      el.addEventListener('click', (event) => {
        event.stopPropagation()
        store.selectSite(site.id)
      })
      const marker = new Marker({ element: el, anchor: 'center' }).setLngLat([site.lon, site.lat]).addTo(map)
      entry = { el, marker, sig: '' }
      markers.set(site.id, entry)
      created = true
    }
    const sig = signature(site)
    if (sig !== entry.sig) {
      entry.el.querySelector('.site__glyph').innerHTML = glyph(site)
      entry.sig = sig
    }
    entry.el.querySelector('.site__label').textContent = site.name
    entry.el.setAttribute('aria-label', `${site.name}: ${siteSummary(site)}, battery ${percent(site.soc)}`)
    const classes = entry.el.classList
    classes.toggle('is-risk', site.status === 'up' && site.risk >= 0.5)
    classes.toggle('is-off', site.status !== 'up')
    classes.toggle('is-selected', site.id === store.selectedSiteId)
    classes.toggle('has-action', pendingSites.has(site.id))
    classes.toggle('is-dim', Boolean(zone) && site.zone !== zone)
    classes.toggle('is-zone', Boolean(zone) && site.zone === zone)
  }
  if (created) declutter()
}

const MIN_GAP = 34
const MAX_SHIFT = 56

function declutter() {
  const items = [...markers.values()].map((entry) => {
    const point = map.project(entry.marker.getLngLat())
    return { entry, x: point.x, y: point.y, dx: 0, dy: 0 }
  })
  for (let pass = 0; pass < 60; pass++) {
    let moved = false
    for (let i = 0; i < items.length; i++) {
      for (let j = i + 1; j < items.length; j++) {
        const a = items[i]
        const b = items[j]
        let vx = b.x + b.dx - (a.x + a.dx)
        let vy = b.y + b.dy - (a.y + a.dy)
        let distance = Math.hypot(vx, vy)
        if (distance >= MIN_GAP) continue
        if (distance < 0.01) {
          vx = Math.cos(i + j)
          vy = Math.sin(i + j)
          distance = 1
        }
        const push = (MIN_GAP - distance) / 2
        a.dx -= (vx / distance) * push
        a.dy -= (vy / distance) * push
        b.dx += (vx / distance) * push
        b.dy += (vy / distance) * push
        moved = true
      }
    }
    if (!moved) break
  }
  for (const item of items) {
    const length = Math.hypot(item.dx, item.dy)
    const scale = length > MAX_SHIFT ? MAX_SHIFT / length : 1
    const dx = item.dx * scale
    const dy = item.dy * scale
    item.entry.marker.setOffset([dx, dy])
    const tether = item.entry.el.querySelector('.site__tether')
    const shifted = Math.hypot(dx, dy) > 4
    tether.style.display = shifted ? 'block' : 'none'
    if (shifted) {
      tether.style.width = `${Math.hypot(dx, dy)}px`
      tether.style.transform = `rotate(${Math.atan2(-dy, -dx)}rad)`
    }
  }
}

function syncDepots() {
  for (const depot of store.meta?.depots ?? []) {
    if (depotMarkers.has(depot.id)) continue
    const el = document.createElement('div')
    el.className = 'depot'
    el.innerHTML = `<span class="depot__mark"></span><span class="depot__label">${depot.name}</span>`
    depotMarkers.set(depot.id, new Marker({ element: el }).setLngLat([depot.lon, depot.lat]).addTo(map))
  }
}

function updateRoutes() {
  if (!map?.getSource('routes')) return
  const jobs = store.data?.jobs ?? []
  map.getSource('routes').setData({
    type: 'FeatureCollection',
    features: jobs.map((job) => ({
      type: 'Feature',
      properties: { kind: job.kind },
      geometry: { type: 'LineString', coordinates: [job.from, job.to] },
    })),
  })
  map.getSource('crews').setData({
    type: 'FeatureCollection',
    features: jobs
      .filter((job) => job.phase === 'en_route')
      .map((job) => ({
        type: 'Feature',
        properties: { kind: job.kind },
        geometry: {
          type: 'Point',
          coordinates: [
            job.from[0] + (job.to[0] - job.from[0]) * job.progress,
            job.from[1] + (job.to[1] - job.from[1]) * job.progress,
          ],
        },
      })),
  })
}

function flyIn() {
  if (flewIn || !store.sites.length) return
  flewIn = true
  const bounds = new LngLatBounds()
  store.sites.forEach((site) => bounds.extend([site.lon, site.lat]))
  map.fitBounds(bounds, { padding: { top: 60, bottom: 60, left: 60, right: 60 }, duration: reducedMotion() ? 0 : 2400, essential: false })
}

async function upgradeBasemap() {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 4000)
  try {
    const response = await fetch(BASEMAP, { signal: controller.signal })
    if (response.ok) map.setStyle(BASEMAP)
  } catch {
    // Offline or blocked: stay on the built-in outline map.
  } finally {
    clearTimeout(timer)
  }
}

onMounted(() => {
  map = new MapLibre({
    container: container.value,
    style: fallbackStyle,
    center: [29.85, -19.0],
    zoom: 5.4,
    minZoom: 5,
    maxZoom: 13,
    attributionControl: { compact: true },
    dragRotate: false,
    pitchWithRotate: false,
  })
  map.touchZoomRotate.disableRotation()
  map.addControl(new NavigationControl({ showCompass: false }), 'top-right')
  map.on('style.load', addOverlays)
  map.on('zoom', () => container.value?.classList.toggle('show-labels', map.getZoom() >= 9.5))
  map.on('zoomend', declutter)
  map.on('resize', declutter)
  map.once('load', () => {
    addOverlays()
    ready.value = true
    syncMarkers()
    syncDepots()
    flyIn()
    upgradeBasemap()
  })
})

onBeforeUnmount(() => map?.remove())

watch(
  () => [store.sites, store.selectedSiteId, store.highlightedZone, store.waiting],
  () => {
    if (!ready.value) return
    syncMarkers()
    syncDepots()
    flyIn()
  },
  { deep: false },
)
watch(() => store.data?.jobs, updateRoutes)
watch(
  () => store.selectedSite,
  (site, previous) => {
    if (site && site.id !== previous?.id && map) {
      map.easeTo({ center: [site.lon, site.lat], zoom: Math.max(map.getZoom(), 8.2), duration: reducedMotion() ? 0 : 700 })
    }
  },
)
</script>

<template>
  <section class="map-wrap" aria-label="Network map">
    <div ref="container" class="map"></div>
    <div class="legend" aria-label="Map legend">
      <p class="legend__title">How to read a site</p>
      <ul>
        <li><span class="dot" style="--c: var(--grid)"></span>On grid</li>
        <li><span class="dot" style="--c: var(--battery)"></span>On battery</li>
        <li><span class="dot" style="--c: var(--generator)"></span>On generator</li>
        <li><span class="dot dot--off" style="--c: var(--dark)"></span>Off air, no power</li>
        <li><span class="dot dot--off" style="--c: var(--link)"></span>Off air, link failed</li>
        <li><span class="diamond"></span>Field crew depot</li>
      </ul>
      <p class="legend__note">The ring shows battery charge. A pulse means the site is at risk or off air. A white dot means an action is waiting for you.</p>
    </div>
  </section>
</template>

<style scoped>
.map-wrap {
  position: relative;
  min-height: 0;
  background: #0b1520;
}

.map {
  position: absolute;
  inset: 0;
}

.map-wrap::after {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(120% 90% at 50% 45%, transparent 55%, rgb(5 11 18 / 0.55) 100%);
  pointer-events: none;
}

.legend {
  position: absolute;
  z-index: 2;
  left: 12px;
  bottom: 12px;
  width: 196px;
  padding: 10px 12px 11px;
  border: 1px solid var(--rule);
  border-radius: var(--radius-m);
  background: rgb(14 25 38 / 0.9);
  backdrop-filter: blur(6px);
  font-size: var(--step--1);
  color: var(--text-2);
}

.legend__title {
  margin-bottom: 6px;
  color: var(--text-1);
  font-weight: 600;
}

.legend ul {
  display: grid;
  gap: 3px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.legend li {
  display: flex;
  align-items: center;
  gap: 8px;
}

.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--c);
  box-shadow: 0 0 0 2px var(--ink-1), 0 0 0 3.5px var(--c);
  margin: 0 3px;
}

.dot--off {
  background: var(--ink-1);
}

.diamond {
  width: 8px;
  height: 8px;
  margin: 0 4px;
  background: var(--text-1);
  transform: rotate(45deg);
}

.legend__note {
  margin-top: 8px;
  line-height: 1.35;
  color: var(--text-3);
}

:deep(.site) {
  width: 40px;
  height: 40px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: none;
  transition: opacity 200ms var(--ease);
}

:deep(.site__glyph) {
  position: relative;
  z-index: 1;
  display: block;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  filter: drop-shadow(0 0 6px rgb(0 0 0 / 0.55));
}

:deep(.town) {
  color: #5d7790;
  font-size: 11px;
  font-weight: 600;
  font-variation-settings: var(--wide);
  letter-spacing: 0.02em;
  pointer-events: none;
  white-space: nowrap;
}

:deep(.town--major) {
  color: #7a93ab;
  font-size: 13px;
}

:deep(.site:hover .site__glyph),
:deep(.site.is-selected .site__glyph) {
  filter: brightness(1.18);
}

:deep(.site.is-selected::after) {
  content: '';
  position: absolute;
  inset: 1px;
  border: 2px solid var(--text-1);
  border-radius: 50%;
}

:deep(.site.is-risk::before),
:deep(.site.is-off::before) {
  content: '';
  position: absolute;
  inset: 4px;
  border-radius: 50%;
  border: 2px solid var(--generator);
  animation: pulse 1.8s var(--ease) infinite;
  pointer-events: none;
}

:deep(.site.is-off::before) {
  border-color: var(--dark);
}

:deep(.site__tether) {
  display: none;
  position: absolute;
  left: 20px;
  top: 20px;
  height: 1px;
  background: rgb(157 176 195 / 0.55);
  transform-origin: 0 50%;
  pointer-events: none;
}

:deep(.site__tether)::after {
  content: '';
  position: absolute;
  right: -2px;
  top: -2px;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--text-2);
}

:deep(.site__badge) {
  position: absolute;
  z-index: 2;
  top: 3px;
  right: 3px;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: var(--text-1);
  box-shadow: 0 0 0 2px var(--ink-1);
  transform: scale(0);
  transition: transform 160ms var(--ease);
}

:deep(.site.has-action .site__badge) {
  transform: scale(1);
}

:deep(.site__label) {
  position: absolute;
  left: 50%;
  top: calc(100% - 2px);
  transform: translateX(-50%);
  padding: 2px 6px;
  border-radius: var(--radius-s);
  background: rgb(9 18 28 / 0.88);
  color: var(--text-2);
  font-size: 11.5px;
  font-weight: 550;
  white-space: nowrap;
  pointer-events: none;
  opacity: 0;
  transition: opacity 150ms var(--ease);
}

:deep(.site:hover .site__label),
:deep(.site:focus-visible .site__label),
:deep(.site.is-selected .site__label),
:deep(.site.is-off .site__label),
.show-labels :deep(.site__label) {
  opacity: 1;
}

:deep(.site.is-dim) {
  opacity: 0.22;
}

:deep(.depot) {
  display: flex;
  align-items: center;
  gap: 6px;
  pointer-events: none;
}

:deep(.depot__mark) {
  width: 9px;
  height: 9px;
  background: var(--text-1);
  transform: rotate(45deg);
  box-shadow: 0 0 0 2px var(--ink-1);
}

:deep(.depot__label) {
  display: none;
  color: var(--text-3);
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
}

.show-labels :deep(.depot__label) {
  display: inline;
}

:deep(.maplibregl-ctrl-group) {
  background: var(--ink-2);
  border: 1px solid var(--rule);
  box-shadow: none;
}

:deep(.maplibregl-ctrl-group button + button) {
  border-top-color: var(--rule);
}

:deep(.maplibregl-ctrl-icon) {
  filter: invert(0.85);
}

:deep(.maplibregl-ctrl-attrib) {
  background: rgb(14 25 38 / 0.8) !important;
  color: var(--text-3);
}

:deep(.maplibregl-ctrl-attrib a) {
  color: var(--text-2);
}

@keyframes pulse {
  0% {
    transform: scale(1);
    opacity: 0.9;
  }
  100% {
    transform: scale(1.9);
    opacity: 0;
  }
}

@media (max-width: 760px) {
  .legend {
    width: auto;
    right: 12px;
  }

  .legend ul {
    grid-template-columns: 1fr 1fr;
  }

  .legend__title,
  .legend__note {
    display: none;
  }

  .map :deep(.site__glyph) {
    transform: scale(0.8);
  }
}
</style>
