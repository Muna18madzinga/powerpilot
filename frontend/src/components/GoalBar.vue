<script setup>
import { computed, ref } from 'vue'
import { useConsole } from '../stores/console'

const store = useConsole()
const text = ref('')
const examples = ['Keep Gweru up tonight', 'Save diesel on rural sites today', 'Protect Kwekwe CBD for the next 6 hours']
const result = computed(() => store.goalResult)
const busy = computed(() => store.pending.has('goal'))

async function submit(value = text.value) {
  const goal = value.trim()
  if (goal.length < 3) return
  const done = await store.setGoal(goal)
  if (done) text.value = ''
}
</script>

<template>
  <section class="goal" aria-labelledby="goal-title">
    <h2 id="goal-title" class="panel-title">Set a goal</h2>
    <form class="goal__form" @submit.prevent="submit()">
      <label for="goal-input" class="visually-hidden">Goal for the network</label>
      <input
        id="goal-input"
        v-model="text"
        type="text"
        autocomplete="off"
        maxlength="200"
        placeholder="Keep Zvishavane up tonight"
      />
      <button class="btn btn--primary" :disabled="busy || text.trim().length < 3">Plan it</button>
    </form>
    <div v-if="!result" class="examples">
      <button v-for="example in examples" :key="example" class="chip" @click="submit(example)">{{ example }}</button>
    </div>

    <div v-else class="plan" role="status">
      <div class="plan__head">
        <p class="plan__quote">{{ result.text }}</p>
        <button class="btn btn--quiet plan__close" aria-label="Clear goal" @click="store.goalResult = null">Clear</button>
      </div>
      <p class="plan__summary">{{ result.summary[0].toUpperCase() + result.summary.slice(1) }}.</p>
      <ul class="plan__steps">
        <li v-for="step in result.steps" :key="step">{{ step }}</li>
      </ul>
    </div>
  </section>
</template>

<style scoped>
.goal {
  display: grid;
  gap: 10px;
}

.goal__form {
  display: flex;
  gap: 6px;
}

.goal__form input {
  flex: 1;
  min-width: 0;
  height: 36px;
  padding: 0 12px;
  border: 1px solid var(--rule-strong);
  border-radius: var(--radius-s);
  background: var(--ink-0);
}

.goal__form input::placeholder {
  color: var(--text-3);
}

.goal__form input:focus {
  border-color: var(--text-2);
  outline: none;
}

.goal__form .btn {
  height: 36px;
}

.examples {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.chip {
  padding: 4px 9px;
  border: 1px solid var(--rule);
  border-radius: 999px;
  background: transparent;
  color: var(--text-2);
  font-size: var(--step--1);
}

.chip:hover {
  color: var(--text-1);
  border-color: var(--text-3);
}

.plan {
  padding: 12px;
  border-radius: var(--radius-m);
  background: var(--ink-2);
  border: 1px solid var(--rule);
}

.plan__head {
  display: flex;
  justify-content: space-between;
  align-items: start;
  gap: 8px;
}

.plan__quote {
  color: var(--text-2);
  font-size: var(--step--1);
}

.plan__quote::before {
  content: '“';
}

.plan__quote::after {
  content: '”';
}

.plan__close {
  height: 22px;
  padding: 0 6px;
  font-size: var(--step--1);
}

.plan__summary {
  margin-top: 4px;
  font-size: var(--step-1);
  font-weight: 650;
  font-variation-settings: var(--semi);
}

.plan__steps {
  display: grid;
  gap: 4px;
  margin: 8px 0 0;
  padding-left: 16px;
  color: var(--text-2);
  font-size: var(--step--1);
  line-height: 1.5;
}
</style>
