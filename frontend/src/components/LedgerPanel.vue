<script setup>
import { computed } from 'vue'
import { useConsole } from '../stores/console'
import { change, compact, dollars, elapsed, integer } from '../lib/format'

const store = useConsole()
const kpis = computed(() => store.data?.kpis)

const rows = computed(() => {
  const k = kpis.value
  if (!k) return []
  const b = k.baseline
  const p = k.powerpilot
  return [
    { label: 'Hours sites were off air', base: b.outage_site_hours, now: p.outage_site_hours, fmt: (v) => `${v.toFixed(1)} h` },
    { label: 'Subscriber-hours lost', base: b.subscriber_hours_lost, now: p.subscriber_hours_lost, fmt: compact },
    {
      label: 'Diesel burned or stolen',
      base: b.diesel_burned_l + b.diesel_stolen_l,
      now: p.diesel_burned_l + p.diesel_stolen_l,
      fmt: (v) => `${integer(v)} L`,
    },
    { label: 'Battery capacity stolen', base: b.battery_stolen_kwh, now: p.battery_stolen_kwh, fmt: (v) => `${v.toFixed(1)} kWh` },
    { label: 'Crew distance driven', base: b.trip_km, now: p.trip_km, fmt: (v) => `${integer(v)} km` },
    { label: 'Operating cost', base: b.total_cost_usd, now: p.total_cost_usd, fmt: dollars },
  ].map((row) => {
    const max = Math.max(row.base, row.now, 1e-9)
    return { ...row, delta: change(row.base, row.now), baseShare: row.base / max, nowShare: row.now / max }
  })
})

const availability = computed(() => kpis.value?.availability)
const saved = computed(() => kpis.value?.savings?.cost_usd ?? 0)

function deltaText(delta) {
  if (delta == null) return 'no change yet'
  if (Math.abs(delta) < 0.005) return 'no change'
  return `${delta < 0 ? '−' : '+'}${Math.abs(delta * 100).toFixed(0)}%`
}
</script>

<template>
  <section class="ledger" aria-labelledby="ledger-title">
    <header class="ledger__head">
      <h2 id="ledger-title" class="panel-title">With PowerPilot vs today</h2>
      <p class="muted">
        Same sites, same load-shedding and the same thefts, run twice for
        {{ kpis ? elapsed(kpis.elapsed_hours) : '…' }}.
      </p>
    </header>

    <div v-if="kpis" class="headline">
      <p class="headline__value">{{ dollars(Math.max(0, saved)) }}</p>
      <p class="headline__label">
        saved so far across 30 sites.
        Availability {{ (availability.baseline * 100).toFixed(2) }}% today,
        {{ (availability.powerpilot * 100).toFixed(2) }}% with PowerPilot.
      </p>
    </div>

    <div class="key" aria-hidden="true">
      <span><i class="swatch swatch--base"></i>Today’s operations</span>
      <span><i class="swatch swatch--now"></i>With PowerPilot</span>
    </div>

    <dl class="rows">
      <div v-for="row in rows" :key="row.label" class="row">
        <dt class="row__label">
          {{ row.label }}
          <span class="row__delta" :class="{ 'is-good': row.delta < 0, 'is-bad': row.delta > 0.005 }">{{ deltaText(row.delta) }}</span>
        </dt>
        <dd class="row__bars">
          <span class="bar bar--base" :style="{ '--w': row.baseShare }">
            <span class="visually-hidden">Today’s operations:</span>{{ row.fmt(row.base) }}
          </span>
          <span class="bar bar--now" :style="{ '--w': row.nowShare }">
            <span class="visually-hidden">With PowerPilot:</span>{{ row.fmt(row.now) }}
          </span>
        </dd>
      </div>
    </dl>
  </section>
</template>

<style scoped>
.ledger {
  display: grid;
  gap: 14px;
}

.ledger__head p {
  margin-top: 4px;
  font-size: var(--step--1);
  line-height: 1.5;
}

.headline {
  display: grid;
  gap: 4px;
  padding: 12px 0 14px;
  border-block: 1px solid var(--rule);
}

.headline__value {
  font-size: var(--step-4);
  font-weight: 800;
  font-variation-settings: var(--wide);
  letter-spacing: -0.03em;
  line-height: 1;
}

.headline__label {
  color: var(--text-2);
  font-size: var(--step--1);
  line-height: 1.5;
}

.key {
  display: flex;
  gap: 14px;
  font-size: var(--step--1);
  color: var(--text-2);
}

.key span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.swatch {
  width: 14px;
  height: 6px;
  border-radius: 2px;
}

.swatch--base {
  background: var(--legacy);
}

.swatch--now {
  background: var(--text-1);
}

.rows {
  display: grid;
  gap: 12px;
  margin: 0;
}

.row__label {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 5px;
  font-size: var(--step--1);
  color: var(--text-2);
}

.row__delta {
  font-weight: 650;
  color: var(--text-3);
}

.row__delta.is-good {
  color: var(--text-1);
}

.row__delta.is-bad {
  color: var(--dark);
}

.row__bars {
  display: grid;
  gap: 2px;
  margin: 0;
}

.bar {
  position: relative;
  display: flex;
  align-items: center;
  height: 16px;
  padding-left: calc(max(var(--w) * (100% - 64px), 4px) + 6px);
  font-size: 11.5px;
  font-variation-settings: var(--semi);
  white-space: nowrap;
}

.bar::before {
  content: '';
  position: absolute;
  left: 0;
  top: 3px;
  bottom: 3px;
  width: max(calc(var(--w) * (100% - 64px)), 4px);
  border-radius: 0 4px 4px 0;
  transition: width 500ms var(--ease);
}

.bar--base {
  color: var(--text-3);
}

.bar--base::before {
  background: var(--legacy);
}

.bar--now {
  color: var(--text-1);
  font-weight: 600;
}

.bar--now::before {
  background: var(--text-1);
}
</style>
