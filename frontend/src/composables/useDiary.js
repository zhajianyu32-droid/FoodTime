import { ref, reactive, computed } from 'vue'
import { api } from './useApi'
import { me } from './useAuth'

const stats = ref({})
const diaryList = ref([])
const diaryFilter = ref('')
const filteredDiary = computed(() => diaryFilter.value ? diaryList.value.filter(d => d.type === diaryFilter.value) : diaryList.value)
const recentDiary = computed(() => diaryList.value.slice(0, 5))
const prefWeights = ref([])
const heatmap = reactive({})
const todayStr = new Date().toISOString().slice(0, 10)
const currentYearMonth = computed(() => `${todayStr.slice(0, 4)}年${todayStr.slice(5, 7)}月`)
const heatmapDays = computed(() => {
  const [y, m] = todayStr.split('-').map(Number)
  const first = new Date(y, m - 1, 1), last = new Date(y, m, 0)
  const firstWk = (first.getDay() + 6) % 7
  const days = []
  for (let i = 0; i < firstWk; i++) days.push(null)
  for (let d = 1; d <= last.getDate(); d++) {
    const ds = `${y}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`
    days.push({ day: d, date: ds, type: heatmap[ds] || '', isToday: ds === todayStr })
  }
  return days.filter(Boolean)
})

async function loadStats() {
  if (!me.value) return
  try { const uid = me.value.user_id || me.value.id; stats.value = await api(`/diary/stats/${uid}`) || {} }
  catch (e) { console.warn(e) }
}
async function loadHeatmap() {
  if (!me.value) return
  try {
    const uid = me.value.user_id || me.value.id
    const list = await api(`/diary/heatmap/${uid}`) || []
    Object.keys(heatmap).forEach(k => delete heatmap[k])
    for (const d of list) heatmap[d.date] = d.type
  } catch (e) { console.warn(e) }
}
async function loadPrefWeights() {
  if (!me.value) return
  try { const uid = me.value.user_id || me.value.id; prefWeights.value = await api(`/preferences/weights/${uid}`) || [] }
  catch (e) { console.warn(e) }
}
async function loadDiaryList() {
  if (!me.value) return
  try { const uid = me.value.user_id || me.value.id; const r = await api(`/diary/list/${uid}?page_size=50`); diaryList.value = r.items || r || [] }
  catch (e) { console.warn(e) }
}

async function refreshDashboard() {
  await Promise.allSettled([loadStats(), loadHeatmap(), loadDiaryList(), loadPrefWeights()])
}

export { stats, diaryList, diaryFilter, filteredDiary, recentDiary, prefWeights, heatmapDays, currentYearMonth, todayStr,
  loadStats, loadHeatmap, loadPrefWeights, loadDiaryList, refreshDashboard }
