<script setup>
import { computed } from 'vue'
import { useConsole } from '../stores/console'
import { siteColor, siteSummary } from '../lib/power'
import { percent } from '../lib/format'

const store = useConsole()
const ORDER = { grid: 0, battery: 1, generator: 2 }

const groups = computed(() => {
  const fleet = store.data?.fleet
  if (!fleet) return []
  return [
    { key: 'grid', label: 'Grid', count: fleet.on_grid, color: 'var(--grid)' },
    { key: 'battery', label: 'Battery', count: fleet.on_battery, color: 'var(--battery)' },
    { key: 'generator', label: 'Generator', count: fleet.on_generator, color: 'var(--generator)' },
    { key: 'off', label: 'Off air', count: fleet.dark + fleet.link_down, color: 'var(--dark)' },
  ]
})

const cells = computed(() =>
  [...store.sites].sort((a, b) => {
    const rank = (s) => (s.status !== 'up' ? 3 : ORDER[s.power_source] ?? 3)
    return rank(a) - rank(b) || a.soc - b.soc
  }),
)
</script>

<template>
  <section class="fleet" aria-labelledby="fleet-title">
    <div class="fleet__head">
      <h2 id="fleet-title" class="panel-title">Power right now</h2>
      <p class="muted">
        {{ store.data?.fleet.at_risk ?? 0 }} at risk, {{ store.data?.fleet.sleeping ?? 0 }} saving power in sleep mode
      </p>
    </div>
    <div class="cells" role="list">
      <button
        v-for="site in cells"
        :key="site.id"
        role="listitem"
        class="cell"
        :class="{ 'is-off': site.status !== 'up', 'is-selected': site.id === store.selectedSiteId }"
        :style="{ '--c': siteColor(site), '--fill': site.status === 'up' ? site.soc : 1 }"
        :title="`${site.name}: ${siteSummary(site)}, battery ${percent(site.soc)}`"
        :aria-label="`${site.name}: ${siteSummary(site)}`"
        @click="store.selectSite(site.id)"
      ></button>
    </div>
    <ul class="counts">
      <li v-for="group in groups" :key="group.key">
        <i :style="{ background: group.color }"></i>
        <span>{{ group.label }}</span>
        <strong>{{ group.count }}</strong>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.fleet {
  display: grid;
  gap: 10px;
}

.fleet__head p {
  margin-top: 3px;
  font-size: var(--step--1);
}

.cells {
  display: grid;
  grid-template-columns: repeat(15, 1fr);
  gap: 3px;
}

.cell {
  position: relative;
  aspect-ratio: 1 / 1.35;
  padding: 0;
  border: 0;
  border-radius: 3px;
  background: var(--ink-3);
  overflow: hidden;
}

.cell::after {
  content: '';
  position: absolute;
  inset: auto 0 0 0;
  height: calc(var(--fill) * 100%);
  background: var(--c);
  transition: height 400ms var(--ease), background-color 300ms var(--ease);
}

.cell.is-off {
  background: var(--dark-soft);
  box-shadow: inset 0 0 0 1.5px var(--c);
}

.cell.is-off::after {
  height: 0;
}

.cell.is-selected {
  outline: 2px solid var(--text-1);
  outline-offset: 1px;
}

.counts {
  display: grid;
  grid-template-columns: repeat(4, auto);
  justify-content: space-between;
  margin: 0;
  padding: 0;
  list-style: none;
  font-size: var(--step--1);
  color: var(--text-2);
}

.counts li {
  display: flex;
  align-items: center;
  gap: 5px;
}

.counts i {
  width: 8px;
  height: 8px;
  border-radius: 2px;
}

.counts strong {
  color: var(--text-1);
  font-weight: 650;
}
</style>
