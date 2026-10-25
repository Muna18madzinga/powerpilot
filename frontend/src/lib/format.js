const timeFormat = new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'Africa/Harare' })
const dayFormat = new Intl.DateTimeFormat('en-GB', { weekday: 'short', day: 'numeric', month: 'short', timeZone: 'Africa/Harare' })

export const clockTime = (iso) => (iso ? timeFormat.format(new Date(iso)) : '--:--')
export const clockDay = (iso) => (iso ? dayFormat.format(new Date(iso)) : '')

export function duration(hours) {
  if (hours == null) return '—'
  if (hours < 1) return `${Math.max(1, Math.round(hours * 60))} min`
  if (hours < 48) {
    const whole = Math.floor(hours)
    const minutes = Math.round((hours - whole) * 4) * 15
    if (minutes === 60) return `${whole + 1} h`
    return minutes ? `${whole} h ${minutes} min` : `${whole} h`
  }
  return `${(hours / 24).toFixed(1)} days`
}

export function elapsed(hours) {
  const days = Math.floor(hours / 24)
  const rest = Math.floor(hours % 24)
  if (!days) return `${rest} h`
  return rest ? `${days} d ${rest} h` : `${days} d`
}

export const integer = (value) => Math.round(value ?? 0).toLocaleString('en-GB')
export const percent = (value, digits = 0) => `${((value ?? 0) * 100).toFixed(digits)}%`
export const dollars = (value) => `$${Math.round(value ?? 0).toLocaleString('en-GB')}`

export function compact(value) {
  const v = value ?? 0
  if (Math.abs(v) >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`
  if (Math.abs(v) >= 10_000) return `${Math.round(v / 1000)}k`
  if (Math.abs(v) >= 1000) return `${(v / 1000).toFixed(1)}k`
  return Math.round(v).toLocaleString('en-GB')
}

export function change(base, now) {
  if (!base) return null
  return (now - base) / base
}

export function ago(minutes) {
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes} min ago`
  return `${duration(minutes / 60)} ago`
}
