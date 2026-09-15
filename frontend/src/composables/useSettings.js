import { ref, reactive, computed } from 'vue'
import { api, TOK } from './useApi'
import { me } from './useAuth'
import { showToast } from './useToast'
import { BUDGET_OPTIONS, COOKING_SKILL_OPTIONS, calcZodiacFromBirth, DISLIKED_TREE, toggleArr, removeArr } from '@/lib/constants'

const pwdForm = reactive({ old: '', pwd: '', pwd2: '', loading: false, error: '', success: '', changed: false })

async function changePassword() {
  if (pwdForm.changed) return // 成功后禁止重复提交（旧 Token 已失效）
  pwdForm.error = ''; pwdForm.success = ''
  if (!pwdForm.old || !pwdForm.pwd || !pwdForm.pwd2) { pwdForm.error = '请填写所有密码字段'; return }
  if (pwdForm.pwd.length < 6) { pwdForm.error = '新密码至少 6 位'; return }
  if (pwdForm.pwd !== pwdForm.pwd2) { pwdForm.error = '两次输入的新密码不一致'; return }
  if (pwdForm.pwd === pwdForm.old) { pwdForm.error = '新密码不能与旧密码相同'; return }
  pwdForm.loading = true
  try {
    await api('/auth/password', { method: 'POST', body: { old_password: pwdForm.old, new_password: pwdForm.pwd } })
    pwdForm.success = '密码修改成功！即将退出并重新登录（所有旧 Token 已失效）'
    pwdForm.changed = true
    pwdForm.old = ''; pwdForm.pwd = ''; pwdForm.pwd2 = ''
    showToast('密码已修改 ✓ 已失效所有旧登录')
    setTimeout(() => { TOK.clear(); me.value = null; showToast('出于安全考虑，请重新登录', 'error') }, 1800)
    return true
  } catch (e) { pwdForm.error = e.message; return false }
  finally { pwdForm.loading = false }
}

const onboarding = reactive({
  completed: false, zodiac: '', chinese_zodiac: '', mbti: '',
  taste_preference: '都行',
  birth_date: new Date(Date.now() - 25 * 365 * 86400000).toISOString().slice(0, 10),
  budget_level: BUDGET_OPTIONS[1],
  cooking_skill: COOKING_SKILL_OPTIONS[3],
  cookware: [], disliked_ingredients: [], cuisines: [],
  _cuisine_other_show: false, _cuisine_other_input: '',
  _custom_disliked: {},
})
const onboardingLoading = ref(false)
const onboardingSaving = ref(false)
const liveZodiac = computed(() => calcZodiacFromBirth(onboarding.birth_date).zodiac)
const liveChinese = computed(() => calcZodiacFromBirth(onboarding.birth_date).chinese)
// Select 组件不允许空字符串作为 value，故用 'none' 占位
const mbtiSelect = computed({
  get: () => onboarding.mbti || 'none',
  set: (v) => { onboarding.mbti = v === 'none' ? '' : String(v || '').toUpperCase() },
})

function dislikeTreePathKey(L1, L2) { return L1 + '/' + L2 }

function countDislikedInL2(L2) {
  if (L2.__custom) return 0
  let c = 0
  for (const it of L2.children || []) { if (onboarding.disliked_ingredients.includes(it)) c++ }
  return c
}
function countDislikedInL1(L1) {
  let c = 0
  for (const L2 of L1.children || []) c += countDislikedInL2(L2)
  for (const L2 of L1.children || []) {
    if (L2.__custom) { const key = dislikeTreePathKey(L1.name, L2.name); c += (onboarding._custom_disliked[key] || []).length }
  }
  return c
}

function addCustomDisliked(L1, L2, inputValue) {
  const key = dislikeTreePathKey(L1, L2)
  const v = (typeof inputValue === 'string' ? inputValue : '').trim()
  if (!v) return
  if (!onboarding._custom_disliked[key]) onboarding._custom_disliked[key] = []
  if (!onboarding._custom_disliked[key].includes(v)) onboarding._custom_disliked[key].push(v)
  if (!onboarding.disliked_ingredients.includes(v)) onboarding.disliked_ingredients.push(v)
}

function removeCustomDisliked(L1, L2, idx, item) {
  const key = dislikeTreePathKey(L1, L2)
  const arr = onboarding._custom_disliked[key] || []
  if (arr[idx] === item) arr.splice(idx, 1)
  removeArr(onboarding.disliked_ingredients, item)
}

function addCustomCuisine() {
  const v = (onboarding._cuisine_other_input || '').trim()
  if (!v) return
  if (!onboarding.cuisines.includes(v)) onboarding.cuisines.push(v)
  onboarding._cuisine_other_input = ''
  onboarding._cuisine_other_show = false
}

async function loadOnboarding() {
  if (!me.value) return
  onboardingLoading.value = true
  try {
    const uid = me.value.user_id || me.value.id
    const p = await api(`/preferences/${uid}`) || {}
    // 优先用后端明确的 onboarding_completed 标记
    onboarding.completed = p.onboarding_completed != null
      ? !!p.onboarding_completed
      : (!!p.zodiac || !!p.chinese_zodiac || !!p.taste_preference)
    onboarding.zodiac = p.zodiac || ''
    onboarding.chinese_zodiac = p.chinese_zodiac || ''
    onboarding.mbti = (p.mbti || '').toUpperCase()
    onboarding.taste_preference = p.taste_preference || '都行'
    // 生日回显：后端已持久化则用后端值，否则保持「今天-25年」默认占位
    onboarding.birth_date = p.birth_date || onboarding.birth_date
    onboarding.budget_level = BUDGET_OPTIONS.includes(p.budget_level) ? p.budget_level
      : ({ '省钱': BUDGET_OPTIONS[0], '正常': BUDGET_OPTIONS[1], '吃好点': BUDGET_OPTIONS[3] })[p.budget_level] || BUDGET_OPTIONS[1]
    onboarding.cooking_skill = COOKING_SKILL_OPTIONS.includes(p.cooking_skill) ? p.cooking_skill
      : ({ '新手': COOKING_SKILL_OPTIONS[1], '一般': COOKING_SKILL_OPTIONS[3], '熟练': COOKING_SKILL_OPTIONS[4] })[p.cooking_skill] || COOKING_SKILL_OPTIONS[3]
    onboarding.cookware = Array.isArray(p.cookware) ? [...p.cookware] : []
    onboarding.disliked_ingredients = Array.isArray(p.disliked_ingredients) ? [...p.disliked_ingredients] : []
    onboarding.cuisines = Array.isArray(p.cuisines) ? [...p.cuisines] : []
    // Rebuild custom disliked：优先用后端持久化的按节点分组；旧数据（无分组）兜底归到「其他/其他」
    const leafSet = new Set()
    for (const L1 of DISLIKED_TREE) for (const L2 of L1.children) {
      if (!L2.__custom) for (const it of L2.children || []) leafSet.add(it)
    }
    const custKey = dislikeTreePathKey('其他', '其他')
    const persisted = (p.custom_disliked && typeof p.custom_disliked === 'object') ? p.custom_disliked : null
    if (persisted) {
      onboarding._custom_disliked = {}
      for (const [k, arr] of Object.entries(persisted)) {
        if (Array.isArray(arr) && arr.length) onboarding._custom_disliked[k] = [...arr]
      }
      if (!onboarding._custom_disliked[custKey]) onboarding._custom_disliked[custKey] = []
    } else {
      onboarding._custom_disliked = { [custKey]: [] }
      for (const it of onboarding.disliked_ingredients) {
        if (!leafSet.has(it)) onboarding._custom_disliked[custKey].push(it)
      }
    }
  } catch (e) { console.warn(e) }
  finally { onboardingLoading.value = false }
}

async function saveOnboarding() {
  if (!onboarding.birth_date) { showToast('请选择出生日期', 'error'); return }
  onboardingSaving.value = true
  try {
    const uid = me.value.user_id || me.value.id
    const res = await api('/onboarding', {
      method: 'POST',
      body: {
        user_id: uid, taste_preference: onboarding.taste_preference, birth_date: onboarding.birth_date,
        mbti: (onboarding.mbti || '').toUpperCase(), disliked_ingredients: onboarding.disliked_ingredients || [],
        cookware: onboarding.cookware || [], budget_level: onboarding.budget_level,
        cooking_skill: onboarding.cooking_skill, cuisines: onboarding.cuisines || [],
        custom_disliked: onboarding._custom_disliked || {},
      }
    })
    onboarding.completed = true
    if (res) {
      onboarding.zodiac = res.zodiac || onboarding.zodiac
      onboarding.chinese_zodiac = res.chinese_zodiac || onboarding.chinese_zodiac
      onboarding.mbti = (res.mbti || onboarding.mbti || '').toUpperCase()
      onboarding.budget_level = res.budget_level || onboarding.budget_level
      onboarding.cooking_skill = res.cooking_skill || onboarding.cooking_skill
      if (Array.isArray(res.cuisines)) onboarding.cuisines = res.cuisines
      if (Array.isArray(res.disliked_ingredients)) onboarding.disliked_ingredients = res.disliked_ingredients
    }
    showToast(onboarding.completed ? '偏好档案已更新 ✓' : 'Onboarding 完成 ✓')
  } catch (e) { showToast(e.message, 'error') }
  finally { onboardingSaving.value = false }
}

export { pwdForm, changePassword, onboarding, onboardingLoading, onboardingSaving, liveZodiac, liveChinese, mbtiSelect,
  loadOnboarding, saveOnboarding, dislikeTreePathKey, countDislikedInL1, countDislikedInL2,
  addCustomDisliked, removeCustomDisliked, addCustomCuisine, toggleArr, removeArr }
