import { ref } from 'vue'

const API_BASE = import.meta.env.VITE_API_BASE || '/api'

/* ---------- JWT Token Manager（localStorage）---------- */
const TOK = {
  get A() { return localStorage.getItem('ft_at') || '' },
  set A(v) { v ? localStorage.setItem('ft_at', v) : localStorage.removeItem('ft_at') },
  get R() { return localStorage.getItem('ft_rt') || '' },
  set R(v) { v ? localStorage.setItem('ft_rt', v) : localStorage.removeItem('ft_rt') },
  clear() { this.A = ''; this.R = '' },
}

/* ---------- API 客户端：自动 JWT / 解包 / 401 refresh / 重放 ---------- */
let _refreshing = null

async function api(path, { method = 'GET', body = null, token = null, raw = false } = {}) {
  const headers = { 'Content-Type': 'application/json' }
  const bearer = token || TOK.A
  if (bearer) headers.Authorization = `Bearer ${bearer}`

  const res = await fetch(`${API_BASE}${path}`, {
    method, headers, body: body ? JSON.stringify(body) : undefined,
  })

  // 401：尝试 refresh，然后重放
  if (res.status === 401 && bearer === TOK.A && TOK.R) {
    try {
      if (!_refreshing) _refreshing = (async () => {
        const rr = await fetch(`${API_BASE}/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: TOK.R }),
        })
        const rjson = await rr.json().catch(() => ({}))
        if (rr.ok && rjson.code === 0 && rjson.data?.access_token) {
          TOK.A = rjson.data.access_token
          if (rjson.data.refresh_token) TOK.R = rjson.data.refresh_token
          return true
        }
        TOK.clear()
        return false
      })()
      const ok = await _refreshing
      _refreshing = null
      if (ok && bearer !== TOK.A) {
        return api(path, { method, body, raw, token: TOK.A })
      }
    } catch (e) { /* 忽略 */ }
  }

  let data = null
  try { data = await res.json() } catch (_) {}

  if (!res.ok || (data && typeof data.code === 'number' && data.code !== 0)) {
    const msg = (data && (data.message || data.detail || data.error)) || `HTTP ${res.status}`
    const err = new Error(msg)
    err.status = res.status
    err.code = data?.code
    throw err
  }
  return raw ? data : (data?.data ?? data)
}

export { api, TOK, API_BASE }
