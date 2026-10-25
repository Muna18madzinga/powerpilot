<script setup>
import { computed } from 'vue'
import { useConsole } from '../stores/console'
import { clockTime } from '../lib/format'

const store = useConsole()

const STEP_MS = 15 * 60 * 1000
const schedule = computed(() => store.data?.loadshedding)
const nowMs = computed(() => (store.meta ? new Date(store.meta.time).getTime() : 0))

function spans(grid) {
  const out = []
  let start = 0
  for (let i = 1; i <= grid.length; i++) {
    if (i === grid.length || grid[i] !== grid[start]) {
      out.push({ on: grid[start], from: start, to: i })
      start = i
    }
  }
  return out
}

function nextChange(grid) {
  const index = grid.findIndex((value) => value !== grid[0])
  if (index < 0) return grid[0] ? 'On all day' : 'Off all day'
  const at = clockTime(new Date(nowMs.value + index * STEP_MS).toISOString())
  return grid[0] ? `On, off at ${at}` : `Off, back at ${at}`
}

const zones = computed(() =>
  (schedule.value?.zones ?? []).map((zone) => ({
    ...zone,
    spans: spans(zone.grid),
    status: nextChange(zone.grid),
    on: zone.grid[0],
  })),
)

const ticks = computed(() => {
  if (!nowMs.value) return []
  return [0, 6, 12, 18, 24].map((h) => ({
    share: h / 24,
    label: h === 0 ? 'Now' : clockTime(new Date(nowMs.value + h * 3600 * 1000).toISOString()),
  }))
})
</script>

<template>
  <section class="loom" aria-labelledby="loom-title">
    <header class="loom__head">
      <h2 id="loom-title" class="panel-title">Load-shedding ahead</h2>
      <p class="muted">
        Stage {{ schedule?.stage ?? 0 }}: each zone loses grid power for {{ schedule?.hours_off_per_day ?? 0 }} h a day.
        Point at a zone to find its sites.
      </p>
    </header>
    <div class="rows" @pointerleave="store.highlightedZone = null">
      <div
        v-for="zone in zones"
        :key="zone.zone"
        class="row"
        :class="{ 'is-active': store.highlightedZone === zone.zone }"
        tabindex="0"
        @pointerenter="store.highlightedZone = zone.zone"
        @focus="store.highlightedZone = zone.zone"
        @blur="store.highlightedZone = null"
      >
        <p class="row__name">
          Zone {{ zone.zone }}
          <span class="faint">{{ zone.sites.length }} sites</span>
        </p>
        <div class="track">
          <span
            v-for="span in zone.spans"
            :key="span.from"
            class="span"
            :class="span.on ? 'span--on' : 'span--off'"
            :style="{ left: `${(span.from / zone.grid.length) * 100}%`, width: `${((span.to - span.from) / zone.grid.length) * 100}%` }"
          ></span>
        </div>
        <p class="row__status" :class="{ 'is-off': !zone.on }">{{ zone.status }}</p>
      </div>
      <div class="axis" aria-hidden="true">
        <span
          v-for="tick in ticks"
          :key="tick.label"
          :style="{ left: `${tick.share * 100}%` }"
          :class="{ 'is-now': tick.label === 'Now' }"
        >{{ tick.label }}</span>
      </div>
    </div>
  </section>
</template>

<style scoped>
.loom {
  display: grid;
  grid-template-columns: 220px 1fr;
  gap: 18px;
  padding: 14px var(--gutter) 12px;
  border-top: 1px solid var(--rule);
  background: var(--ink-1);
}

.loom__head p {
  margin-top: 4px;
  font-size: var(--step--1);
  line-height: 1.5;
}

.rows {
  --label: 96px;
  --status: 124px;
  display: grid;
  gap: 4px;
  align-content: start;
}

.row {
  display: grid;
  grid-template-columns: var(--label) 1fr var(--status);
  align-items: center;
  gap: 10px;
  border-radius: var(--radius-s);
  outline: none;
}

.row__name {
  display: flex;
  justify-content: space-between;
  font-size: var(--step--1);
  font-weight: 600;
}

.track {
  position: relative;
  height: 14px;
  border-radius: 3px;
  overflow: hidden;
  background: var(--ink-0);
}

.span {
  position: absolute;
  top: 0;
  bottom: 0;
}

.span--on {
  background: var(--grid-soft);
  box-shadow: inset 0 1px 0 rgb(63 140 219 / 0.6);
}

.span--off {
  background: repeating-linear-gradient(45deg, #1a2b3c 0 2px, #0b1520 2px 6px);
}

.row:hover .span--on,
.row.is-active .span--on,
.row:focus-visible .span--on {
  background: rgb(63 140 219 / 0.42);
}

.row:focus-visible .track {
  outline: 2px solid var(--text-1);
  outline-offset: 2px;
}

.row__status {
  font-size: var(--step--1);
  color: var(--text-2);
  white-space: nowrap;
}

.row__status.is-off {
  color: var(--text-1);
  font-weight: 600;
}

.axis {
  position: relative;
  height: 14px;
  margin: 2px var(--status) 0 calc(var(--label) + 10px);
  margin-right: calc(var(--status) + 10px);
}

.axis span {
  position: absolute;
  transform: translateX(-50%);
  font-size: 10.5px;
  color: var(--text-3);
  white-space: nowrap;
}

.axis span:first-child {
  transform: none;
}

.axis span:last-child {
  transform: translateX(-100%);
}

.axis .is-now {
  color: var(--text-1);
  font-weight: 650;
}

@media (max-width: 1080px) {
  .loom {
    grid-template-columns: 1fr;
    gap: 10px;
  }
}

@media (max-width: 760px) {
  .loom {
    padding: 12px 16px;
  }

  .rows {
    --label: 58px;
    --status: 0px;
  }

  .row__name .faint,
  .row__status {
    display: none;
  }
}
</style>
