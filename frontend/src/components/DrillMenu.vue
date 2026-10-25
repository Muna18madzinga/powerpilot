<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useConsole } from '../stores/console'

const emit = defineEmits(['close'])
const store = useConsole()
const root = ref(null)

const target = computed(() => store.selectedSite)
const drills = computed(() => [
  { kind: 'battery_theft', label: 'Battery theft', hint: 'Modules removed over two hours' },
  { kind: 'fuel_theft', label: 'Diesel siphoning', hint: 'Fuel drained from the generator tank', needsGenerator: true },
  { kind: 'link_fault', label: 'Transmission link failure', hint: 'Site off air with healthy power' },
  { kind: 'grid_fault', label: 'Unplanned ZESA fault', hint: 'Four hours without grid power' },
])

function run(drill) {
  store.drill(drill.kind, target.value?.id)
  emit('close')
}

function onPointer(event) {
  if (root.value && !root.value.contains(event.target) && !event.target.closest('.drill')) emit('close')
}

function onKey(event) {
  if (event.key === 'Escape') emit('close')
}

onMounted(() => {
  document.addEventListener('pointerdown', onPointer)
  document.addEventListener('keydown', onKey)
})
onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', onPointer)
  document.removeEventListener('keydown', onKey)
})
</script>

<template>
  <div ref="root" class="menu" role="menu">
    <p class="menu__intro">
      Stage a problem at
      <strong>{{ target ? target.name : 'a random rural site' }}</strong>
      and watch PowerPilot respond.
      <span v-if="!target" class="faint">Select a site on the map to choose it.</span>
    </p>
    <button
      v-for="drill in drills"
      :key="drill.kind"
      class="menu__item"
      role="menuitem"
      :disabled="drill.needsGenerator && target && !target.generator_kva"
      @click="run(drill)"
    >
      <span>{{ drill.label }}</span>
      <span class="faint">{{ drill.hint }}</span>
    </button>
    <div class="menu__foot">
      <button class="btn btn--quiet" role="menuitem" @click="store.reset(); emit('close')">Restart the run</button>
    </div>
  </div>
</template>

<style scoped>
.menu {
  position: absolute;
  right: 0;
  top: calc(100% + 8px);
  z-index: 30;
  width: 300px;
  padding: 12px;
  border: 1px solid var(--rule-strong);
  border-radius: var(--radius-m);
  background: var(--ink-2);
  box-shadow: 0 18px 40px rgb(0 0 0 / 0.45);
}

.menu__intro {
  margin-bottom: 8px;
  padding: 0 4px;
  color: var(--text-2);
  font-size: var(--step--1);
  line-height: 1.5;
}

.menu__intro strong {
  color: var(--text-1);
  font-weight: 600;
}

.menu__intro .faint {
  display: block;
}

.menu__item {
  display: grid;
  gap: 1px;
  width: 100%;
  padding: 8px;
  border: 0;
  border-radius: var(--radius-s);
  background: transparent;
  text-align: left;
}

.menu__item span:first-child {
  font-weight: 600;
}

.menu__item span:last-child {
  font-size: var(--step--1);
}

.menu__item:hover:not(:disabled) {
  background: var(--ink-3);
}

.menu__item:disabled {
  opacity: 0.4;
  cursor: default;
}

.menu__foot {
  margin-top: 6px;
  padding-top: 8px;
  border-top: 1px solid var(--rule);
}

@media (max-width: 760px) {
  .menu {
    position: fixed;
    left: 16px;
    right: 16px;
    top: auto;
    bottom: 16px;
    width: auto;
  }
}
</style>
