<script setup>
import { computed } from 'vue'
import { useConsole } from '../stores/console'
import { JOB, siteColor, siteSummary } from '../lib/power'
import { clockTime, duration, integer, percent } from '../lib/format'
import PowerTape from './PowerTape.vue'
import RecommendationItem from './RecommendationItem.vue'

const store = useConsole()
const site = computed(() => store.selectedSite)
const detail = computed(() => (store.siteDetail?.id === site.value?.id ? store.siteDetail : null))
const recs = computed(() => (store.data?.recommendations ?? []).filter((r) => r.site_id === site.value?.id))

const riskText = computed(() => {
  const s = site.value
  if (!s) return ''
  if (s.status !== 'up') return 'Off air now'
  if (s.dark_in_hours != null) return `Goes dark in ${duration(s.dark_in_hours)}`
  return 'Holds through the next 24 h'
})

const readings = computed(() => {
  const s = site.value
  if (!s) return []
  const items = [
    {
      label: 'Battery',
      value: percent(s.soc),
      note: `${s.battery_kwh} of ${s.battery_rated_kwh} kWh installed`,
      warn: s.battery_kwh < s.battery_rated_kwh * 0.6,
    },
    s.tank_l
      ? {
          label: 'Diesel',
          value: `${integer(s.fuel_l)} L`,
          note: s.fuel_runway_hours != null ? `Lasts about ${duration(s.fuel_runway_hours)}` : `${integer(s.tank_l)} L tank`,
          warn: s.fuel_runway_hours != null && s.fuel_runway_hours < 36,
        }
      : { label: 'Diesel', value: 'None', note: 'No generator on site' },
    { label: 'Risk, next 6 h', value: percent(s.risk), note: riskText.value, warn: s.risk >= 0.5 },
    { label: 'Load', value: `${s.load_kw.toFixed(1)} kW`, note: s.sleeping ? 'Capacity layers asleep' : 'All layers on air' },
    { label: 'Traffic', value: percent(s.traffic), note: 'Of busy-hour peak' },
    { label: 'Subscribers', value: integer(s.subscribers), note: `${s.area === 'peri' ? 'Peri-urban' : s.area[0].toUpperCase() + s.area.slice(1)}, zone ${s.zone}` },
  ]
  return items
})

const equipment = computed(() => {
  const s = site.value
  if (!s) return []
  return [
    ['Radio layers', s.layers.join(', ')],
    ['Grid supply', s.has_grid ? 'ZESA connected' : 'Off-grid'],
    ['Generator', s.generator_kva ? `${s.generator_kva} kVA` : 'None'],
    ['Solar', s.solar_kw ? `${s.solar_kw} kW` : 'None'],
    ['Security', s.guarded ? 'Guard on site' : 'Unguarded'],
  ]
})
</script>

<template>
  <section v-if="site" class="detail" aria-labelledby="detail-title">
    <button class="btn btn--quiet back" @click="store.selectSite(null)">
      <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M10 3 5 8l5 5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" /></svg>
      All sites
    </button>

    <header class="head">
      <p class="head__id">{{ site.id }}, {{ site.town }}</p>
      <h2 id="detail-title" class="head__name">{{ site.name }}</h2>
      <p class="head__status" :style="{ '--c': siteColor(site) }">
        <i></i>{{ siteSummary(site) }}<template v-if="site.status === 'up' && site.power_source !== 'grid'">, grid is off</template>
      </p>
    </header>

    <dl class="readings">
      <div v-for="item in readings" :key="item.label" class="reading" :class="{ 'is-warn': item.warn }">
        <dt>{{ item.label }}</dt>
        <dd>
          <span class="reading__value">{{ item.value }}</span>
          <span class="reading__note">{{ item.note }}</span>
        </dd>
      </div>
    </dl>

    <PowerTape v-if="detail" :detail="detail" :now="store.meta.time" />
    <p v-else class="loading muted">Loading the last 12 hours…</p>

    <section v-if="recs.length" class="block">
      <h3 class="block__title">Actions for this site</h3>
      <RecommendationItem v-for="rec in recs" :key="rec.id" :rec="rec" :start-open="rec.status === 'pending'" />
    </section>

    <section v-if="site.jobs.length" class="block">
      <h3 class="block__title">Crews</h3>
      <ul class="jobs">
        <li v-for="job in site.jobs" :key="job.id">
          <strong>{{ JOB[job.kind] }}</strong>
          <span class="muted">On site {{ clockTime(job.eta) }}, finished by {{ clockTime(job.done) }}</span>
        </li>
      </ul>
    </section>

    <section class="block">
      <h3 class="block__title">Equipment</h3>
      <dl class="equipment">
        <template v-for="[label, value] in equipment" :key="label">
          <dt>{{ label }}</dt>
          <dd>{{ value }}</dd>
        </template>
      </dl>
    </section>
  </section>
</template>

<style scoped>
.detail {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 16px;
}

.back {
  justify-self: start;
  margin-left: -10px;
}

.back svg {
  width: 14px;
  height: 14px;
}

.head__id {
  color: var(--text-3);
  font-size: var(--step--1);
}

.head__name {
  margin-top: 2px;
  font-size: var(--step-3);
  font-weight: 800;
  font-variation-settings: var(--wide);
  letter-spacing: -0.02em;
  line-height: 1.05;
}

.head__status {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  color: var(--text-1);
  font-weight: 550;
}

.head__status i {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--c);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--c) 30%, transparent);
}

.readings {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1px;
  margin: 0;
  border: 1px solid var(--rule);
  border-radius: var(--radius-m);
  background: var(--rule);
  overflow: hidden;
}

.reading {
  padding: 10px 10px 11px;
  background: var(--ink-1);
}

.reading dt {
  color: var(--text-3);
  font-size: 11.5px;
}

.reading dd {
  display: grid;
  gap: 2px;
  margin: 3px 0 0;
}

.reading__value {
  font-size: var(--step-2);
  font-weight: 700;
  font-variation-settings: var(--semi);
  line-height: 1.1;
}

.reading__note {
  color: var(--text-2);
  font-size: 11.5px;
  line-height: 1.35;
}

.reading.is-warn .reading__value {
  color: var(--generator);
}

.loading {
  font-size: var(--step--1);
}

.block {
  display: grid;
  gap: 4px;
}

.block__title {
  font-size: var(--step-0);
  font-weight: 650;
}

.jobs {
  display: grid;
  gap: 6px;
  margin: 0;
  padding: 0;
  list-style: none;
  font-size: var(--step--1);
}

.jobs li {
  display: grid;
}

.equipment {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 4px 16px;
  margin: 0;
  font-size: var(--step--1);
}

.equipment dt {
  color: var(--text-3);
}

.equipment dd {
  margin: 0;
}

@media (max-width: 420px) {
  .readings {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
