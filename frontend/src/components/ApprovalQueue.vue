<script setup>
import { computed } from 'vue'
import { useConsole } from '../stores/console'
import RecommendationItem from './RecommendationItem.vue'

const store = useConsole()
const autonomy = computed(() => store.meta?.autonomy)

const emptyText = computed(() => {
  if (autonomy.value === 'autopilot') return 'Autopilot is on. Actions run on their own and show under In progress.'
  return 'Nothing needs you right now. PowerPilot is watching every site.'
})
</script>

<template>
  <section class="queue" aria-labelledby="queue-title">
    <header class="queue__head">
      <h2 id="queue-title" class="panel-title">
        Waiting for you
        <span v-if="store.waiting.length" class="count">{{ store.waiting.length }}</span>
      </h2>
      <button
        v-if="store.waiting.length > 1"
        class="btn"
        :disabled="store.pending.has('all')"
        @click="store.approveAll()"
      >
        Approve all
      </button>
    </header>

    <TransitionGroup v-if="store.waiting.length" name="rec" tag="div" class="list">
      <RecommendationItem v-for="(rec, index) in store.waiting" :key="rec.id" :rec="rec" :start-open="index === 0" />
    </TransitionGroup>
    <p v-else class="empty muted">{{ emptyText }}</p>

    <template v-if="store.inProgress.length">
      <h3 class="sub">In progress</h3>
      <div class="list">
        <RecommendationItem v-for="rec in store.inProgress.slice(0, 8)" :key="rec.id" :rec="rec" />
      </div>
    </template>
  </section>
</template>

<style scoped>
.queue {
  display: grid;
  gap: 4px;
}

.queue__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 32px;
}

.queue__head h2 {
  display: flex;
  align-items: center;
  gap: 8px;
}

.count {
  display: grid;
  place-items: center;
  min-width: 22px;
  height: 22px;
  padding: 0 6px;
  border-radius: 999px;
  background: var(--text-1);
  color: var(--ink-1);
  font-size: var(--step--1);
  font-weight: 750;
}

.sub {
  margin-top: 18px;
  font-size: var(--step-0);
  font-weight: 600;
  color: var(--text-2);
}

.empty {
  padding: 12px 0;
  border-bottom: 1px solid var(--rule);
  font-size: var(--step--1);
  line-height: 1.5;
}

.rec-enter-active {
  transition: opacity 260ms var(--ease), transform 260ms var(--ease);
}

.rec-enter-from {
  opacity: 0;
  transform: translateY(-6px);
}

.rec-leave-active {
  transition: opacity 180ms var(--ease);
}

.rec-leave-to {
  opacity: 0;
}
</style>
