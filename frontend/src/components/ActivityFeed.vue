<script setup>
import { computed } from 'vue'
import { useConsole } from '../stores/console'
import { clockTime } from '../lib/format'

const store = useConsole()

const TONE = {
  down: 'var(--dark)',
  restored: 'var(--battery)',
  recommendation: 'var(--generator)',
  approved: 'var(--text-1)',
  job_done: 'var(--battery)',
  rejected: 'var(--text-3)',
  scenario: 'var(--link)',
  goal: 'var(--grid)',
  schedule: 'var(--grid)',
  watch: 'var(--text-3)',
}

const entries = computed(() => (store.data?.log ?? []).slice(0, 40))
</script>

<template>
  <section class="feed" aria-labelledby="feed-title">
    <h2 id="feed-title" class="panel-title">What happened</h2>
    <ol v-if="entries.length" class="list">
      <li v-for="(entry, index) in entries" :key="`${entry.step}-${index}-${entry.message}`">
        <button
          class="entry"
          :disabled="!entry.site_id"
          @click="entry.site_id && store.selectSite(entry.site_id)"
        >
          <time class="entry__time">{{ clockTime(entry.time) }}</time>
          <i class="entry__mark" :style="{ background: TONE[entry.kind] ?? 'var(--text-3)' }"></i>
          <span class="entry__text">{{ entry.message }}</span>
        </button>
      </li>
    </ol>
    <p v-else class="empty muted">Nothing yet. Events appear here as the network runs.</p>
  </section>
</template>

<style scoped>
.feed {
  display: grid;
  gap: 8px;
}

.list {
  margin: 0;
  padding: 0;
  list-style: none;
}

.entry {
  display: grid;
  grid-template-columns: 40px 8px 1fr;
  align-items: baseline;
  gap: 8px;
  width: 100%;
  padding: 5px 0;
  border: 0;
  border-bottom: 1px solid var(--rule);
  background: transparent;
  text-align: left;
  font-size: var(--step--1);
  line-height: 1.4;
}

.entry:disabled {
  cursor: default;
}

.entry:not(:disabled):hover .entry__text {
  color: var(--text-1);
}

.entry__time {
  color: var(--text-3);
  font-variation-settings: var(--semi);
}

.entry__mark {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  transform: translateY(-1px);
}

.entry__text {
  color: var(--text-2);
}

.empty {
  font-size: var(--step--1);
}
</style>
