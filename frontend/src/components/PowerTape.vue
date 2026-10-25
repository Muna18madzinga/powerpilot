<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { clockTime } from '../lib/format'

const props = defineProps({
  detail: { type: Object, required: true },
  now: { type: String, required: true },
})

const PAST = 48
const FUTURE = 96
const STEP_MS = 15 * 60 * 1000
const HEIGHT = 196
const PLOT = { top: 10, right: 12, bottom: 50, left: 34 }

const root = ref(null)
const width = ref(320)
const hover = ref(null)
let observer

onMounted(() => {
  observer = new ResizeObserver(([entry]) => {
    width.value = Math.max(280, entry.contentRect.width)
  })
  observer.observe(root.value)
})
onBeforeUnmount(() => observer?.disconnect())

const plotWidth = computed(() => width.value - PLOT.left - PLOT.right)
const plotHeight = HEIGHT - PLOT.top - PLOT.bottom
const x = (offset) => PLOT.left + ((offset + PAST) / (PAST + FUTURE)) * plotWidth.value
const y = (soc) => PLOT.top + (1 - soc) * plotHeight

function smooth(values) {
  return values.map((v, i) => {
    const window = values.slice(Math.max(0, i - 1), i + 2).filter((x) => x != null)
    return v == null ? v : window.reduce((a, b) => a + b, 0) / window.length
  })
}

const past = computed(() => {
  const history = props.detail.history.slice(-PAST)
  const pilot = smooth(history.map((h) => h.soc))
  const baseline = smooth(props.detail.baseline_soc.slice(-history.length))
  return history.map((h, i) => ({ ...h, soc: pilot[i], offset: i - history.length + 1, legacy: baseline[i] }))
})

const future = computed(() =>
  props.detail.projected_soc.slice(0, FUTURE).map((soc, i) => ({
    offset: i + 1,
    soc,
    grid: props.detail.schedule[i]?.grid ?? true,
  })),
)

function path(points, key) {
  return points
    .filter((p) => p[key] != null)
    .map((p, i) => `${i ? 'L' : 'M'}${x(p.offset).toFixed(1)},${y(p[key]).toFixed(1)}`)
    .join('')
}

const pilotPath = computed(() => path(past.value, 'soc'))
const legacyPath = computed(() => path(past.value, 'legacy'))
const forecastPath = computed(() => {
  const last = past.value.at(-1)
  const points = last ? [{ offset: 0, soc: last.soc }, ...future.value] : future.value
  return path(points, 'soc')
})

function runs(points, test) {
  const spans = []
  let start = null
  points.forEach((p, i) => {
    if (test(p) && start === null) start = p.offset
    const ends = start !== null && (!test(p) || i === points.length - 1)
    if (ends) {
      const end = test(p) ? p.offset + 1 : p.offset
      spans.push({ x: x(start - 1), w: Math.max(1, x(end - 1) - x(start - 1)) })
      start = null
    }
  })
  return spans
}

const gridOff = computed(() => [...runs(past.value, (p) => !p.grid), ...runs(future.value, (p) => !p.grid)])
const generator = computed(() => runs(past.value, (p) => p.gen))
const sleeping = computed(() => runs(past.value, (p) => p.sleep))
const offAir = computed(() => [...runs(past.value, (p) => p.status !== 'up'), ...runs(future.value, (p) => p.soc === 0)])

const nowMs = computed(() => new Date(props.now).getTime())
const ticks = computed(() =>
  [-12, -6, 0, 6, 12, 18, 24]
    .filter((h) => h * 4 >= -past.value.length)
    .map((h) => ({ hour: h, x: x(h * 4), label: h === 0 ? 'Now' : clockTime(new Date(nowMs.value + h * 4 * STEP_MS).toISOString()) })),
)

const stripY = HEIGHT - PLOT.bottom + 10

function onMove(event) {
  const rect = root.value.getBoundingClientRect()
  const px = event.clientX - rect.left
  const offset = Math.round(((px - PLOT.left) / plotWidth.value) * (PAST + FUTURE) - PAST)
  if (offset < -past.value.length + 1 || offset > FUTURE) {
    hover.value = null
    return
  }
  const pastPoint = past.value.find((p) => p.offset === offset)
  const futurePoint = future.value.find((p) => p.offset === offset)
  const point = pastPoint ?? futurePoint
  if (!point) return
  hover.value = {
    x: x(offset),
    y: y(point.soc),
    time: clockTime(new Date(nowMs.value + offset * STEP_MS).toISOString()),
    soc: point.soc,
    legacy: pastPoint?.legacy,
    grid: point.grid,
    gen: pastPoint?.gen,
    forecast: !pastPoint,
  }
}
</script>

<template>
  <figure class="tape">
    <figcaption class="tape__caption">
      <span>Battery charge, past 12 h and next 24 h</span>
      <span class="tape__legend" aria-hidden="true">
        <span><i class="line line--pilot"></i>With PowerPilot</span>
        <span><i class="line line--legacy"></i>Today’s operations</span>
        <span><i class="line line--forecast"></i>Forecast</span>
        <span><i class="box box--grid"></i>Grid off</span>
        <span><i class="box box--gen"></i>Generator</span>
      </span>
    </figcaption>
    <div ref="root" class="tape__plot" @pointermove="onMove" @pointerleave="hover = null">
      <svg :width="width" :height="HEIGHT" role="img" :aria-label="`Battery charge chart for ${detail.name}`">
        <defs>
          <pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="6" height="6" fill="rgb(9 18 28 / 0.6)" />
            <line x1="0" y1="0" x2="0" y2="6" stroke="#243649" stroke-width="2" />
          </pattern>
        </defs>

        <rect
          v-for="(band, i) in gridOff"
          :key="`g${i}`"
          :x="band.x"
          :y="PLOT.top"
          :width="band.w"
          :height="plotHeight"
          fill="url(#hatch)"
        />

        <g class="axis">
          <line v-for="v in [0, 0.5, 1]" :key="v" :x1="PLOT.left" :x2="width - PLOT.right" :y1="y(v)" :y2="y(v)" />
          <text v-for="v in [0, 0.5, 1]" :key="`t${v}`" :x="PLOT.left - 6" :y="y(v) + 4" text-anchor="end">{{ v * 100 }}%</text>
        </g>

        <path :d="legacyPath" class="series series--legacy" />
        <path :d="forecastPath" class="series series--forecast" />
        <path :d="pilotPath" class="series series--pilot" />

        <line class="now" :x1="x(0)" :x2="x(0)" :y1="PLOT.top - 4" :y2="stripY + 22" />

        <g class="strips">
          <text :x="PLOT.left - 6" :y="stripY + 6" text-anchor="end">Gen</text>
          <rect v-for="(s, i) in generator" :key="`gen${i}`" :x="s.x" :y="stripY" :width="s.w" height="7" rx="2" class="strip--gen" />
          <text :x="PLOT.left - 6" :y="stripY + 18" text-anchor="end">Sleep</text>
          <rect v-for="(s, i) in sleeping" :key="`sl${i}`" :x="s.x" :y="stripY + 12" :width="s.w" height="7" rx="2" class="strip--sleep" />
          <rect v-for="(s, i) in offAir" :key="`off${i}`" :x="s.x" :y="PLOT.top + plotHeight - 3" :width="s.w" height="3" class="strip--off" />
        </g>

        <g class="xaxis">
          <text v-for="tick in ticks" :key="tick.hour" :x="tick.x" :y="HEIGHT - 4" text-anchor="middle" :class="{ 'is-now': tick.label === 'Now' }">
            {{ tick.label }}
          </text>
        </g>

        <g v-if="hover" class="cursor">
          <line :x1="hover.x" :x2="hover.x" :y1="PLOT.top" :y2="PLOT.top + plotHeight" />
          <circle :cx="hover.x" :cy="hover.y" r="4.5" />
        </g>
      </svg>

      <div
        v-if="hover"
        class="tip"
        :style="{ left: `${Math.min(hover.x + 12, width - 190)}px` }"
      >
        <p class="tip__time">{{ hover.time }}{{ hover.forecast ? ', forecast' : '' }}</p>
        <p>Battery {{ Math.round(hover.soc * 100) }}%<span v-if="hover.forecast" class="faint"> expected</span></p>
        <p v-if="hover.legacy != null" class="faint">Today’s operations {{ Math.round(hover.legacy * 100) }}%</p>
        <p class="faint">{{ hover.grid ? 'Grid on' : 'Grid off' }}{{ hover.gen ? ', generator running' : '' }}</p>
      </div>
    </div>
  </figure>
</template>

<style scoped>
.tape {
  min-width: 0;
  margin: 0;
}

.tape__caption {
  display: grid;
  gap: 6px;
  margin-bottom: 8px;
  font-size: var(--step--1);
  color: var(--text-2);
}

.tape__caption > span:first-child {
  color: var(--text-1);
  font-weight: 600;
}

.tape__legend {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 12px;
}

.tape__legend span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.line {
  width: 16px;
  height: 0;
  border-top: 2px solid var(--text-1);
}

.line--legacy {
  border-top: 2px dashed var(--legacy);
}

.line--forecast {
  border-top: 2px dotted var(--text-2);
}

.box {
  width: 10px;
  height: 10px;
  border-radius: 2px;
}

.box--grid {
  background: repeating-linear-gradient(45deg, #243649 0 2px, rgb(9 18 28 / 0.6) 2px 5px);
  border: 1px solid #243649;
}

.box--gen {
  background: var(--generator);
}

.tape__plot {
  position: relative;
  width: 100%;
  min-width: 0;
  overflow: hidden;
  touch-action: pan-y;
}

svg {
  display: block;
}

.axis line {
  stroke: var(--rule);
  stroke-width: 1;
}

.axis text,
.strips text,
.xaxis text {
  fill: var(--text-3);
  font-size: 10.5px;
  font-family: var(--font);
}

.xaxis .is-now {
  fill: var(--text-1);
  font-weight: 650;
}

.series {
  fill: none;
  stroke-linejoin: round;
  stroke-linecap: round;
}

.series--pilot {
  stroke: var(--text-1);
  stroke-width: 2;
}

.series--legacy {
  stroke: var(--legacy);
  stroke-width: 1.6;
  stroke-dasharray: 5 4;
}

.series--forecast {
  stroke: var(--text-2);
  stroke-width: 1.8;
  stroke-dasharray: 1.5 4;
}

.now {
  stroke: var(--text-2);
  stroke-width: 1;
}

.strip--gen {
  fill: var(--generator);
}

.strip--sleep {
  fill: var(--link);
  opacity: 0.75;
}

.strip--off {
  fill: var(--dark);
}

.cursor line {
  stroke: var(--text-2);
  stroke-dasharray: 2 3;
}

.cursor circle {
  fill: var(--text-1);
  stroke: var(--ink-1);
  stroke-width: 2;
}

.tip {
  position: absolute;
  top: 4px;
  width: 178px;
  padding: 8px 10px;
  border: 1px solid var(--rule-strong);
  border-radius: var(--radius-s);
  background: var(--ink-0);
  font-size: var(--step--1);
  line-height: 1.5;
  pointer-events: none;
}

.tip__time {
  font-weight: 650;
}
</style>
