<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useConsole } from './stores/console'
import TopBar from './components/TopBar.vue'
import NetworkMap from './components/NetworkMap.vue'
import SheddingLoom from './components/SheddingLoom.vue'
import LedgerPanel from './components/LedgerPanel.vue'
import FleetStrip from './components/FleetStrip.vue'
import ActivityFeed from './components/ActivityFeed.vue'
import ModelNotes from './components/ModelNotes.vue'
import GoalBar from './components/GoalBar.vue'
import ApprovalQueue from './components/ApprovalQueue.vue'
import SiteDetail from './components/SiteDetail.vue'

const store = useConsole()
const query = window.matchMedia('(max-width: 1279px)')
const compact = ref(query.matches)
const tab = ref('actions')
const onQuery = (event) => (compact.value = event.matches)

onMounted(() => {
  store.start()
  query.addEventListener('change', onQuery)
})
onBeforeUnmount(() => query.removeEventListener('change', onQuery))

watch(
  () => store.selectedSiteId,
  (id) => {
    if (id && compact.value) tab.value = 'actions'
  },
)

const tabs = computed(() => [
  { id: 'actions', label: store.selectedSite ? 'Site' : 'Actions', count: store.waiting.length },
  { id: 'results', label: 'Results' },
  { id: 'activity', label: 'Activity' },
])
</script>

<template>
  <div class="shell" :class="{ 'is-compact': compact }">
    <TopBar class="shell__bar" />

    <aside v-if="!compact" class="shell__left scroll" aria-label="Results and activity">
      <LedgerPanel />
      <FleetStrip />
      <ActivityFeed />
      <ModelNotes />
    </aside>

    <main class="shell__main">
      <NetworkMap class="shell__map" />
      <SheddingLoom />
    </main>

    <aside class="shell__right" aria-label="Actions">
      <nav v-if="compact" class="tabs" role="tablist">
        <button
          v-for="item in tabs"
          :key="item.id"
          role="tab"
          :aria-selected="tab === item.id"
          :class="{ 'is-on': tab === item.id }"
          @click="tab = item.id"
        >
          {{ item.label }}
          <span v-if="item.count" class="tabs__count">{{ item.count }}</span>
        </button>
      </nav>

      <div class="shell__pane scroll">
        <template v-if="!compact || tab === 'actions'">
          <SiteDetail v-if="store.selectedSite" />
          <template v-else>
            <GoalBar />
            <ApprovalQueue />
          </template>
        </template>
        <template v-else-if="tab === 'results'">
          <LedgerPanel />
          <FleetStrip />
          <ModelNotes />
        </template>
        <ActivityFeed v-else />
      </div>
    </aside>

    <Transition name="toast">
      <p v-if="store.toast" :key="store.toast.id" class="toast" :class="`is-${store.toast.tone}`" role="status">
        {{ store.toast.text }}
      </p>
    </Transition>

    <div v-if="!store.data" class="boot" role="status">
      <p>{{ store.error ? 'Waiting for the PowerPilot service…' : 'Loading the network…' }}</p>
    </div>
  </div>
</template>

<style scoped>
.shell {
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr) 400px;
  grid-template-rows: auto minmax(0, 1fr);
  grid-template-areas:
    'bar bar bar'
    'left main right';
  height: 100%;
  min-height: 0;
}

.shell__bar {
  grid-area: bar;
}

.shell__left {
  grid-area: left;
  display: flex;
  flex-direction: column;
  gap: 28px;
  padding: 18px var(--gutter) 28px;
  border-right: 1px solid var(--rule);
}

.shell__main {
  grid-area: main;
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto;
  min-height: 0;
  min-width: 0;
}

.shell__map {
  min-height: 320px;
}

.shell__right {
  grid-area: right;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  min-height: 0;
  border-left: 1px solid var(--rule);
}

.shell__left > *,
.shell__pane > * {
  flex-shrink: 0;
  min-width: 0;
}

.shell__pane {
  display: flex;
  flex-direction: column;
  gap: 26px;
  padding: 18px var(--gutter) 32px;
  min-height: 0;
}

.tabs {
  display: flex;
  gap: 4px;
  padding: 8px var(--gutter) 0;
  border-bottom: 1px solid var(--rule);
}

.tabs button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 10px 10px;
  border: 0;
  border-bottom: 2px solid transparent;
  background: transparent;
  color: var(--text-2);
  font-weight: 600;
}

.tabs button.is-on {
  color: var(--text-1);
  border-bottom-color: var(--text-1);
}

.tabs__count {
  display: grid;
  place-items: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 999px;
  background: var(--text-1);
  color: var(--ink-1);
  font-size: 11px;
  font-weight: 750;
}

.is-compact {
  grid-template-columns: minmax(0, 1fr) 380px;
  grid-template-areas:
    'bar bar'
    'main right';
}

.toast {
  position: fixed;
  left: 50%;
  bottom: 24px;
  z-index: 50;
  max-width: min(520px, calc(100vw - 32px));
  padding: 10px 16px;
  border-radius: var(--radius-m);
  background: var(--text-1);
  color: var(--ink-1);
  font-weight: 600;
  transform: translateX(-50%);
  box-shadow: 0 12px 30px rgb(0 0 0 / 0.4);
}

.toast.is-error {
  background: var(--dark);
  color: #fff;
}

.toast-enter-active,
.toast-leave-active {
  transition: opacity 200ms var(--ease), transform 200ms var(--ease);
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translate(-50%, 8px);
}

.boot {
  position: fixed;
  inset: 0;
  z-index: 60;
  display: grid;
  place-items: center;
  background: var(--ink-1);
  color: var(--text-2);
}

@media (max-width: 760px) {
  .shell,
  .is-compact {
    display: flex;
    flex-direction: column;
    height: auto;
    min-height: 100%;
  }

  .shell__map {
    height: 56vh;
    min-height: 340px;
  }

  .shell__right {
    border-left: 0;
    border-top: 1px solid var(--rule);
  }

  .tabs {
    position: sticky;
    top: 0;
    z-index: 5;
    padding: 6px 16px 0;
    background: var(--ink-1);
  }

  .shell__pane {
    padding: 16px 16px 40px;
  }
}
</style>
