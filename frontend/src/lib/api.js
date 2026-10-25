const BASE = import.meta.env.VITE_API_URL ?? ''

async function request(method, path, body) {
  const response = await fetch(`${BASE}${path}`, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}))
    throw new Error(detail.detail ?? `${method} ${path} failed with ${response.status}`)
  }
  return response.json()
}

export const api = {
  state: () => request('GET', '/api/state'),
  site: (id) => request('GET', `/api/sites/${id}`),
  approve: (id) => request('POST', `/api/recommendations/${id}/approve`),
  reject: (id) => request('POST', `/api/recommendations/${id}/reject`),
  approveAll: () => request('POST', '/api/recommendations/approve-all'),
  goal: (text) => request('POST', '/api/goals', { text }),
  scenario: (payload) => request('POST', '/api/scenarios', payload),
  settings: (payload) => request('PUT', '/api/settings', payload),
  clock: (payload) => request('PUT', '/api/clock', payload),
  step: (count) => request('POST', `/api/clock/step?count=${count}`),
  reset: () => request('POST', '/api/reset'),
}
