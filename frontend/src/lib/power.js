const SOURCE = {
  grid: { label: 'Grid', color: '#3f8cdb' },
  battery: { label: 'Battery', color: '#22a98a' },
  generator: { label: 'Generator', color: '#c98012' },
  none: { label: 'No power', color: '#e5455a' },
}

const STATUS = {
  up: { label: 'On air' },
  dark: { label: 'Off air, no power', color: '#e5455a' },
  link_down: { label: 'Off air, link failed', color: '#9e6be8' },
}

export const URGENCY = {
  critical: { label: 'Critical', color: '#e5455a' },
  high: { label: 'High', color: '#c98012' },
  medium: { label: 'Medium', color: '#3f8cdb' },
  low: { label: 'Low', color: '#6b8095' },
}

export const JOB = {
  refuel: 'Refuel',
  replace_battery: 'Battery swap',
  repair_link: 'Link repair',
  security: 'Security',
  mobile_genset: 'Mobile generator',
}

export function siteColor(site) {
  if (site.status === 'dark') return STATUS.dark.color
  if (site.status === 'link_down') return STATUS.link_down.color
  return SOURCE[site.power_source]?.color ?? SOURCE.none.color
}

export function siteSummary(site) {
  if (site.status !== 'up') return STATUS[site.status].label
  return `On ${SOURCE[site.power_source].label.toLowerCase()}`
}
