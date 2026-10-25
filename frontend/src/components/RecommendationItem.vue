<script setup>
import { computed, ref } from 'vue'
import { useConsole } from '../stores/console'
import { URGENCY } from '../lib/power'
import { ago, clockTime } from '../lib/format'

const props = defineProps({ rec: { type: Object, required: true }, startOpen: Boolean })
const store = useConsole()
const open = ref(props.startOpen)

const urgency = computed(() => URGENCY[props.rec.urgency])
const busy = computed(() => store.pending.has(props.rec.id))
const waiting = computed(() => props.rec.status === 'pending')
const statusLine = computed(() => {
  const rec = props.rec
  if (rec.status === 'auto') return rec.eta ? `Running on its own. On site ${clockTime(rec.eta)}` : 'Running on its own'
  if (rec.status === 'approved') return rec.eta ? `Approved. On site ${clockTime(rec.eta)}` : 'Approved'
  return `${urgency.value.label}, raised ${ago(rec.age_minutes)}`
})
</script>

<template>
  <article class="rec" :class="[`is-${rec.urgency}`, { 'is-open': open, 'is-waiting': waiting }]" :style="{ '--u': urgency.color }">
    <div class="rec__head">
      <button class="rec__title" :aria-expanded="open" @click="open = !open">{{ rec.title }}</button>
      <button
        v-if="rec.site_id"
        class="rec__site"
        :class="{ 'is-current': rec.site_id === store.selectedSiteId }"
        @click="store.selectSite(rec.site_id)"
      >
        {{ rec.site_name }}
      </button>
      <span v-else class="rec__site">{{ rec.site_name }}</span>
      <span class="rec__meta">{{ statusLine }}</span>
    </div>

    <p class="rec__benefit">{{ rec.benefit }}</p>

    <ol v-if="open" class="trail">
      <li v-for="(step, index) in rec.trail" :key="step.stage" class="trail__step">
        <span class="trail__n">{{ index + 1 }}</span>
        <div>
          <p class="trail__stage">{{ step.stage }}</p>
          <p class="trail__text">{{ step.text }}</p>
        </div>
      </li>
    </ol>

    <div v-if="waiting" class="rec__actions">
      <button class="btn btn--primary" :disabled="busy" @click="store.approve(rec)">Approve</button>
      <button class="btn btn--quiet" :disabled="busy" @click="store.reject(rec)">Dismiss</button>
      <button class="btn btn--quiet rec__why" @click="open = !open">{{ open ? 'Hide reasoning' : 'Why?' }}</button>
    </div>
  </article>
</template>

<style scoped>
.rec {
  position: relative;
  padding: 12px 0 12px 14px;
  border-bottom: 1px solid var(--rule);
}

.rec::before {
  content: '';
  position: absolute;
  left: 0;
  top: 14px;
  bottom: 14px;
  width: 3px;
  border-radius: 2px;
  background: var(--u);
}

.rec:not(.is-waiting)::before {
  opacity: 0.35;
}

.rec__head {
  display: grid;
  grid-template-columns: 1fr auto;
  column-gap: 10px;
  row-gap: 2px;
}

.rec__title {
  padding: 0;
  border: 0;
  background: transparent;
  text-align: left;
  font-size: var(--step-1);
  font-weight: 650;
  font-variation-settings: var(--semi);
}

.rec__site {
  align-self: start;
  padding: 1px 7px;
  background: transparent;
  border: 1px solid var(--rule-strong);
  border-radius: 999px;
  color: var(--text-2);
  font-size: var(--step--1);
  font-weight: 550;
  white-space: nowrap;
}

button.rec__site:hover,
.rec__site.is-current {
  color: var(--text-1);
  border-color: var(--text-3);
}

.rec__meta {
  grid-column: 1 / -1;
  color: var(--text-3);
  font-size: var(--step--1);
}

.is-waiting.is-critical .rec__meta {
  color: var(--dark);
}

.rec__benefit {
  margin-top: 6px;
  color: var(--text-2);
  font-size: var(--step-0);
}

.trail {
  display: grid;
  gap: 10px;
  margin: 12px 0 2px;
  padding: 0;
  list-style: none;
}

.trail__step {
  display: grid;
  grid-template-columns: 20px 1fr;
  gap: 10px;
}

.trail__n {
  display: grid;
  place-items: center;
  width: 20px;
  height: 20px;
  border: 1px solid var(--rule-strong);
  border-radius: 50%;
  color: var(--text-2);
  font-size: 11px;
  font-weight: 650;
}

.trail__stage {
  font-size: var(--step--1);
  font-weight: 650;
  color: var(--text-1);
}

.trail__text {
  margin-top: 1px;
  color: var(--text-2);
  font-size: var(--step--1);
  line-height: 1.5;
}

.rec__actions {
  display: flex;
  gap: 6px;
  margin-top: 10px;
}

.rec__why {
  margin-left: auto;
}
</style>
