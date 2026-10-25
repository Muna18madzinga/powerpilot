<script setup>
import { computed, ref } from 'vue'
import { useConsole } from '../stores/console'
import { clockDay, clockTime } from '../lib/format'
import DrillMenu from './DrillMenu.vue'

const store = useConsole()
const drillOpen = ref(false)

const meta = computed(() => store.meta)
const clock = computed(() => meta.value?.clock)
const stage = computed(() => meta.value?.stage ?? 0)
const hoursOff = computed(() => Math.min(24, stage.value * 4))

const autonomyHelp = {
  advise: 'Every change waits for an engineer',
  assist: 'Radio and power controls run on their own. Field crews wait for approval',
  autopilot: 'Everything runs on its own and is logged',
}
</script>

<template>
  <header class="bar">
    <div class="brand">
      <svg class="brand__mark" viewBox="0 0 32 32" aria-hidden="true">
        <circle cx="16" cy="16" r="11" fill="none" stroke="#243649" stroke-width="3.2" />
        <circle cx="16" cy="16" r="11" fill="none" stroke="#22a98a" stroke-width="3.2" stroke-linecap="round"
                stroke-dasharray="48 70" transform="rotate(-90 16 16)" />
        <circle cx="16" cy="16" r="4.2" fill="#e8eef4" />
      </svg>
      <div>
        <h1 class="brand__name">PowerPilot</h1>
        <p class="brand__scope">Midlands pilot, 30 base stations</p>
      </div>
    </div>

    <div class="clock" :title="'Simulated network time'">
      <span class="clock__day">{{ clockDay(meta?.time) }}</span>
      <span class="clock__time">{{ clockTime(meta?.time) }}</span>
      <span class="clock__tag">Simulated</span>
    </div>

    <div class="controls">
      <div class="group" role="group" aria-label="Load-shedding stage">
        <span class="group__label">Load-shedding</span>
        <div class="stepper">
          <button class="stepper__btn" :disabled="stage <= 0" aria-label="Lower stage" @click="store.setStage(stage - 1)">−</button>
          <span class="stepper__value" :title="`${hoursOff} h off per zone each day`">Stage {{ stage }}</span>
          <button class="stepper__btn" :disabled="stage >= 6" aria-label="Raise stage" @click="store.setStage(stage + 1)">+</button>
        </div>
      </div>

      <div class="group" role="radiogroup" aria-label="Autonomy">
        <span class="group__label">Autonomy</span>
        <div class="segmented">
          <button
            v-for="level in meta?.autonomy_levels ?? []"
            :key="level"
            role="radio"
            :aria-checked="meta?.autonomy === level"
            :class="{ 'is-on': meta?.autonomy === level }"
            :title="autonomyHelp[level]"
            @click="store.setAutonomy(level)"
          >
            {{ level[0].toUpperCase() + level.slice(1) }}
          </button>
        </div>
      </div>

      <div class="group" role="group" aria-label="Simulation speed">
        <span class="group__label">Run</span>
        <div class="segmented">
          <button
            class="play"
            :aria-label="clock?.running ? 'Pause' : 'Play'"
            @click="store.setClock({ running: !clock?.running })"
          >
            <svg v-if="clock?.running" viewBox="0 0 16 16" aria-hidden="true"><rect x="3.5" y="3" width="3" height="10" rx="1" /><rect x="9.5" y="3" width="3" height="10" rx="1" /></svg>
            <svg v-else viewBox="0 0 16 16" aria-hidden="true"><path d="M4.5 2.8v10.4L13 8z" /></svg>
          </button>
          <button
            v-for="speed in clock?.speeds ?? []"
            :key="speed"
            :class="{ 'is-on': clock?.speed === speed }"
            :aria-label="`${speed} times speed`"
            @click="store.setClock({ speed })"
          >
            {{ speed }}×
          </button>
          <button title="Jump six hours ahead" @click="store.skip(6)">+6 h</button>
        </div>
      </div>

      <div class="drill">
        <button class="btn" :aria-expanded="drillOpen" @click="drillOpen = !drillOpen">Run a drill</button>
        <DrillMenu v-if="drillOpen" @close="drillOpen = false" />
      </div>
    </div>

    <p v-if="!store.connected && store.error" class="offline" role="status">
      Can’t reach the PowerPilot service. Start it with <code>uvicorn powerpilot.api:app</code> in the backend folder.
    </p>
  </header>
</template>

<style scoped>
.bar {
  position: relative;
  display: flex;
  align-items: center;
  gap: 28px;
  min-height: 64px;
  padding: 10px var(--gutter);
  border-bottom: 1px solid var(--rule);
  background: var(--ink-1);
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.brand__mark {
  width: 30px;
  height: 30px;
}

.brand__name {
  font-size: var(--step-2);
  font-weight: 800;
  font-variation-settings: var(--wide);
  letter-spacing: -0.01em;
  line-height: 1;
}

.brand__scope {
  margin-top: 3px;
  font-size: var(--step--1);
  color: var(--text-3);
}

.clock {
  display: grid;
  grid-template-columns: auto auto;
  align-items: baseline;
  column-gap: 10px;
  padding-left: 28px;
  border-left: 1px solid var(--rule);
}

.clock__day {
  grid-column: 1 / -1;
  font-size: var(--step--1);
  color: var(--text-2);
}

.clock__time {
  font-size: var(--step-3);
  font-weight: 700;
  font-variation-settings: var(--wide);
  line-height: 1;
  letter-spacing: -0.02em;
}

.clock__tag {
  font-size: 11px;
  color: var(--text-3);
}

.controls {
  display: flex;
  align-items: flex-end;
  gap: 18px;
  margin-left: auto;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.group {
  display: grid;
  gap: 4px;
}

.group__label {
  font-size: 11.5px;
  color: var(--text-3);
}

.stepper,
.segmented {
  display: flex;
  height: 32px;
  border: 1px solid var(--rule-strong);
  border-radius: var(--radius-s);
  overflow: hidden;
}

.stepper__btn {
  width: 30px;
  border: 0;
  background: transparent;
  font-size: var(--step-1);
}

.stepper__btn:hover:not(:disabled) {
  background: var(--ink-3);
}

.stepper__btn:disabled {
  color: var(--text-3);
  cursor: default;
}

.stepper__value {
  display: grid;
  place-items: center;
  min-width: 70px;
  padding: 0 6px;
  border-inline: 1px solid var(--rule);
  font-weight: 650;
  font-variation-settings: var(--semi);
}

.segmented button {
  min-width: 36px;
  padding: 0 10px;
  border: 0;
  border-right: 1px solid var(--rule);
  background: transparent;
  color: var(--text-2);
  font-size: var(--step-0);
  font-weight: 500;
}

.segmented button:last-child {
  border-right: 0;
}

.segmented button:hover {
  color: var(--text-1);
  background: var(--ink-3);
}

.segmented button.is-on {
  background: var(--text-1);
  color: var(--ink-1);
  font-weight: 650;
}

.play {
  display: grid;
  place-items: center;
}

.play svg {
  width: 14px;
  height: 14px;
  fill: currentColor;
}

.drill {
  position: relative;
}

.offline {
  position: absolute;
  left: 0;
  right: 0;
  top: 100%;
  z-index: 20;
  padding: 8px var(--gutter);
  background: var(--dark);
  color: #fff;
  font-weight: 500;
}

.offline code {
  padding: 1px 5px;
  border-radius: 3px;
  background: rgb(0 0 0 / 0.25);
}

@media (max-width: 1280px) {
  .clock {
    padding-left: 18px;
  }

  .bar {
    gap: 18px;
  }
}

@media (max-width: 1400px) {
  .bar {
    flex-wrap: wrap;
  }

  .controls {
    width: 100%;
    margin-left: 0;
    justify-content: flex-start;
  }
}

@media (max-width: 760px) {
  .bar {
    padding: 10px 16px;
    gap: 12px;
  }

  .clock {
    margin-left: auto;
    padding-left: 0;
    border-left: 0;
    text-align: right;
  }

  .clock__time {
    font-size: var(--step-2);
  }

  .controls {
    gap: 10px;
  }

  .group__label {
    display: none;
  }
}
</style>
