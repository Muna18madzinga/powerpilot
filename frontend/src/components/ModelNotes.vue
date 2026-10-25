<script setup>
import { computed } from 'vue'
import { useConsole } from '../stores/console'

const store = useConsole()
const models = computed(() => store.meta?.models ?? [])

const LABELS = {
  roc_auc: 'ROC AUC',
  average_precision: 'Average precision',
  positive_rate: 'Outage rate in data',
  recall_on_tamper_steps: 'Tamper steps caught',
  false_alarm_rate: 'False alarm rate',
}

function show(key, value) {
  if (key === 'rows') return null
  if (key === 'false_alarm_rate' || key === 'positive_rate' || key === 'recall_on_tamper_steps') {
    return `${(value * 100).toFixed(key === 'false_alarm_rate' ? 2 : 1)}%`
  }
  return value.toFixed(3)
}
</script>

<template>
  <section class="notes" aria-labelledby="notes-title">
    <h2 id="notes-title" class="panel-title">How it decides</h2>
    <article v-for="model in models" :key="model.name" class="model">
      <h3>{{ model.name }}</h3>
      <p class="faint">{{ model.algorithm }}</p>
      <dl>
        <template v-for="(value, key) in model.metrics" :key="key">
          <template v-if="show(key, value)">
            <dt>{{ LABELS[key] ?? key }}</dt>
            <dd>{{ show(key, value) }}</dd>
          </template>
        </template>
      </dl>
    </article>
    <p class="caveat">
      Every site, reading and event here is simulated. Scores are measured on held-out simulated days.
      Accuracy on NetOne telemetry is what the pilot will measure.
    </p>
  </section>
</template>

<style scoped>
.notes {
  display: grid;
  gap: 10px;
}

.model h3 {
  font-size: var(--step-0);
  font-weight: 600;
}

.model p {
  font-size: var(--step--1);
}

dl {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 2px 12px;
  margin: 6px 0 0;
  font-size: var(--step--1);
}

dt {
  color: var(--text-2);
}

dd {
  margin: 0;
  font-weight: 600;
  font-variation-settings: var(--semi);
}

.caveat {
  padding-top: 10px;
  border-top: 1px solid var(--rule);
  color: var(--text-3);
  font-size: var(--step--1);
  line-height: 1.5;
}
</style>
