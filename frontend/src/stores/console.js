import { defineStore } from 'pinia'
import { api } from '../lib/api'

const POLL_MS = 700
const DETAIL_POLL_MS = 1500

export const useConsole = defineStore('console', {
  state: () => ({
    data: null,
    connected: false,
    error: null,
    selectedSiteId: null,
    siteDetail: null,
    highlightedZone: null,
    pending: new Set(),
    goalResult: null,
    toast: null,
  }),

  getters: {
    meta: (s) => s.data?.meta,
    sites: (s) => s.data?.sites ?? [],
    selectedSite(s) {
      return this.sites.find((site) => site.id === s.selectedSiteId) ?? null
    },
    waiting: (s) => (s.data?.recommendations ?? []).filter((r) => r.status === 'pending'),
    inProgress: (s) => (s.data?.recommendations ?? []).filter((r) => r.status === 'approved' || r.status === 'auto'),
  },

  actions: {
    async start() {
      const loop = async () => {
        await this.refresh()
        setTimeout(loop, POLL_MS)
      }
      const detailLoop = async () => {
        if (this.selectedSiteId) await this.refreshSite()
        setTimeout(detailLoop, DETAIL_POLL_MS)
      }
      loop()
      detailLoop()
    },

    async refresh() {
      try {
        this.data = await api.state()
        this.connected = true
        this.error = null
      } catch (error) {
        this.connected = false
        this.error = error.message
      }
    },

    async refreshSite() {
      const id = this.selectedSiteId
      try {
        const detail = await api.site(id)
        if (this.selectedSiteId === id) this.siteDetail = detail
      } catch {
        this.siteDetail = null
      }
    },

    selectSite(id) {
      if (this.selectedSiteId === id) return
      this.selectedSiteId = id
      this.siteDetail = null
      if (id) this.refreshSite()
    },

    async run(key, action, message) {
      this.pending.add(key)
      try {
        const result = await action()
        if (message) this.notify(typeof message === 'function' ? message(result) : message)
        await this.refresh()
        return result
      } catch (error) {
        this.notify(error.message, 'error')
      } finally {
        this.pending.delete(key)
      }
    },

    notify(text, tone = 'info') {
      const id = Date.now()
      this.toast = { id, text, tone }
      setTimeout(() => {
        if (this.toast?.id === id) this.toast = null
      }, 3800)
    },

    approve(rec) {
      return this.run(rec.id, () => api.approve(rec.id), `Approved: ${rec.title.toLowerCase()} at ${rec.site_name}`)
    },
    reject(rec) {
      return this.run(rec.id, () => api.reject(rec.id), `Dismissed for 4 hours: ${rec.title.toLowerCase()}`)
    },
    approveAll() {
      return this.run('all', api.approveAll, (r) => `Approved ${r.approved} action${r.approved === 1 ? '' : 's'}`)
    },
    async setGoal(text) {
      const result = await this.run('goal', () => api.goal(text))
      if (result) this.goalResult = result
      return result
    },
    setAutonomy(autonomy) {
      return this.run('settings', () => api.settings({ autonomy }))
    },
    setStage(stage) {
      return this.run('settings', () => api.settings({ stage }), `Load-shedding set to Stage ${stage}`)
    },
    setClock(payload) {
      return this.run('clock', () => api.clock(payload))
    },
    skip(hours) {
      return this.run('clock', () => api.step(hours * 4), `Skipped ahead ${hours} h`)
    },
    drill(kind, siteId) {
      return this.run('drill', () => api.scenario({ kind, site_id: siteId ?? null }), (r) => `Drill started: ${r.applied}`)
    },
    async reset() {
      this.goalResult = null
      this.selectSite(null)
      return this.run('reset', api.reset, 'Run restarted')
    },
  },
})
