import { ref } from 'vue'
import { api, TOK } from './useApi'

const me = ref(null)
const quota = ref({
  LLM_RECIPES_QUOTA: 0, LLM_RECIPES_TOTAL: 100,
  LLM_FORTUNE_QUOTA: 0, LLM_FORTUNE_TOTAL: 10,
  LLM_CHAT_QUOTA: 0, LLM_CHAT_TOTAL: 50,
})
const env = ref('dev')

async function reloadMe() {
  try {
    const data = await api('/auth/me')
    me.value = {
      ...data.user || data,
      user_id: data.user?.user_id || data.user_id || data.user?.id || null,
    }
    const q = data.quota || {}
    Object.assign(quota.value, {
      LLM_RECIPES_QUOTA: q.recipe?.used ?? 0,
      LLM_RECIPES_TOTAL: q.recipe?.limit ?? 100,
      LLM_FORTUNE_QUOTA: q.fortune?.used ?? 0,
      LLM_FORTUNE_TOTAL: q.fortune?.limit ?? 10,
      LLM_CHAT_QUOTA: q.chat?.used ?? 0,
      LLM_CHAT_TOTAL: q.chat?.limit ?? 50,
    })
    env.value = q.env || 'dev'
    return true
  } catch (e) {
    TOK.clear()
    me.value = null
    return false
  }
}

async function login(username, password) {
  const tok = await api('/auth/login', { method: 'POST', body: { username, password } })
  TOK.A = tok.access_token
  TOK.R = tok.refresh_token
  await reloadMe()
  const redirect = sessionStorage.getItem('ft_redirect') || '/dashboard'
  sessionStorage.removeItem('ft_redirect')
  return tok
}

async function register(username, password, phone = '') {
  const payload = { username, password }
  if (phone) payload.phone = phone
  const tok = await api('/auth/register', { method: 'POST', body: payload })
  TOK.A = tok.access_token
  TOK.R = tok.refresh_token
  await reloadMe()
  return tok
}

function logout() {
  TOK.clear()
  me.value = null
}

export { me, quota, env, reloadMe, login, register, logout }
