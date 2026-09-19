import { ref, reactive, computed } from 'vue'
import { api } from './useApi'
import { me } from './useAuth'
import { isExpiring, parseCost } from '@/lib/constants'
import { showToast } from './useToast'

const ingredients = ref([])
const recipes = ref([])

/* ---------- Zone 状态管理（前端本地） ---------- */
// zoneMap: { [ingredientId]: 'pool' | 'freezer' | 'fridge' | 'cooking' }
const zoneMap = reactive({})
const dragSource = ref(null)   // 拖拽源 zone 名
const dragIngId = ref(null)    // 当前拖拽的食材 ID
const dragOverZone = ref(null) // 当前悬停的 zone 名（用于高亮）

const ingById = computed(() => Object.fromEntries(ingredients.value.map(i => [i.id, i])))
const availableIngredients = computed(() => ingredients.value.filter(i => i.status !== 'expired' && i.status !== 'used_up'))
const expiredCount = computed(() => ingredients.value.filter(i => i.status === 'expired').length)
const expiringCount = computed(() => ingredients.value.filter(i => i.status !== 'expired' && i.status !== 'used_up' && isExpiring(i)).length)
const loading = reactive({ ingredients: false, recipes: false })

// 各 zone 的食材列表
const poolItems = computed(() => ingredients.value.filter(i => zoneMap[i.id] === 'pool'))
const freezerItems = computed(() => ingredients.value.filter(i => zoneMap[i.id] === 'freezer'))
const fridgeItems = computed(() => ingredients.value.filter(i => zoneMap[i.id] === 'fridge'))
const cookingItems = computed(() => ingredients.value.filter(i => zoneMap[i.id] === 'cooking'))

async function loadIngredients() {
  if (!me.value) return
  loading.ingredients = true
  try {
    const uid = me.value.user_id || me.value.id
    const list = await api(`/ingredients/${uid}?page_size=100`)
    ingredients.value = list.items || list || []
    // 从后端 location 字段恢复 zone 状态，缺失则默认 pool
    for (const ing of ingredients.value) {
      zoneMap[ing.id] = ing.location || 'pool'
    }
  } catch (e) { showToast('加载冰箱失败：' + e.message, 'error') }
  finally { loading.ingredients = false }
}

async function addIngredient(name, category, quantity, unit, shelf_days = null) {
  if (!me.value || !name.trim()) return
  try {
    const body = { user_id: me.value.user_id || me.value.id, name: name.trim(), category, quantity: quantity || '1', unit: unit || '份' }
    if (shelf_days) body.shelf_days = shelf_days
    const ing = await api('/ingredients', { method: 'POST', body })
    ingredients.value.unshift(ing)
    zoneMap[ing.id] = 'pool' // 新食材进入待选池
    showToast('已加入待选池 ✓')
  } catch (e) { showToast(e.message, 'error') }
}

async function deleteIngredient(ing) {
  try {
    await api(`/ingredients/${ing.id}`, { method: 'DELETE' })
    ingredients.value = ingredients.value.filter(x => x.id !== ing.id)
    delete zoneMap[ing.id]
    showToast('已删除')
  } catch (e) { showToast('删除失败：' + e.message, 'error') }
}

async function editIngredient(ing, payload) {
  try {
    const updated = await api(`/ingredients/${ing.id}`, { method: 'PUT', body: payload })
    const idx = ingredients.value.findIndex(x => x.id === ing.id)
    if (idx >= 0) ingredients.value.splice(idx, 1, updated)
    showToast('食材已更新 ✓')
    return updated
  } catch (e) { showToast(e.message, 'error') }
}

async function markIngredient(ing, status) {
  return editIngredient(ing, { status })
}

/* ---------- 拖拽逻辑 ---------- */
function onDragStart(ing, zone) {
  dragSource.value = zone
  dragIngId.value = ing.id
}

function onDragEnd() {
  dragSource.value = null
  dragIngId.value = null
  dragOverZone.value = null
}

function onDragOver(zone) {
  dragOverZone.value = zone
}

function onDragLeave(zone) {
  if (dragOverZone.value === zone) dragOverZone.value = null
}

function moveToZone(ingId, zone) {
  const ing = ingById.value[ingId]
  if (!ing) return
  // 过期食材不能拖入做菜区
  if (zone === 'cooking' && (ing.status === 'expired' || ing.status === 'used_up')) {
    showToast('该食材不可用：' + (ing.status === 'expired' ? '已过期' : '已用完'), 'error')
    return
  }
  zoneMap[ingId] = zone
  // 同步到后端持久化
  api(`/ingredients/${ingId}`, { method: 'PUT', body: { location: zone } }).catch(() => {})
}

async function recommendRecipes() {
  if (cookingItems.value.length === 0 || !me.value) return
  loading.recipes = true; recipes.value = []
  try {
    const list = cookingItems.value.map(i => i.name)
    const res = await api('/recipes/recommend', {
      method: 'POST',
      body: { user_id: me.value.user_id || me.value.id, ingredient_names: list }
    })
    recipes.value = res.recipes || []
    showToast(`LLM 返回 ${recipes.value.length} 道菜谱 ✓`)
  } catch (e) { showToast('推荐失败：' + e.message, 'error') }
  finally { loading.recipes = false }
}

/** 从 "15分钟" / "15min" / "15" 提取分钟数，提取不到返回 null */
function parseMinutes(val) {
  if (!val) return null
  const m = String(val).match(/(\d+)/)
  return m ? parseInt(m[1], 10) : null
}

async function saveCookRecord(r) {
  try {
    const body = {
      user_id: me.value.user_id || me.value.id,
      dish_name: r.name,
      ai_recommend_id: r.cache_id || '',
      estimated_cost: parseCost(r.estimated_cost),
      cooking_time: parseMinutes(r.cooking_time),
      rating: 3,
      mood: '',
      difficulty: '简单',
      note: '',
      tags: [],
    }
    await api('/diary/cook', { method: 'POST', body })
    showToast('✅ 已记录为今日做饭！偏好权重已更新')
  } catch (e) { showToast('记录失败：' + e.message, 'error') }
}

/** 计算一道菜谱真正需要补的食材（missing_ingredients - 食材库 available） */
function realMissingCount(r) {
  const missing = r?.missing_ingredients || []
  if (missing.length === 0) return 0
  const existing = new Set(
    ingredients.value
      .filter(i => i.status === 'available')
      .map(i => i.name.trim())
  )
  return missing.filter(n => !existing.has(String(n).trim())).length
}

/** 购物单同步：只加"食材库 available 中没有"的食材 */
async function addToShopping(items) {
  try {
    // 排除食材库中已存在且 available 的食材，避免重复加入购物单
    const existing = new Set(
      ingredients.value
        .filter(i => i.status === 'available')
        .map(i => i.name.trim())
    )
    const toAdd = items.filter(n => !existing.has(String(n).trim())).map(String)

    if (toAdd.length === 0) {
      showToast('🎉 这些食材已在冰箱里，无需补货')
      return 0
    }

    for (const name of toAdd) {
      await api('/shopping', {
        method: 'POST',
        body: { user_id: me.value.user_id || me.value.id, name, category: '其他', quantity: '1', priority: 'normal' }
      })
    }
    showToast(`已将 ${toAdd.length} 项加入购物单（已排除 ${items.length - toAdd.length} 项库存食材）`)
    return toAdd.length
  } catch (e) { showToast('加入购物单失败：' + e.message, 'error'); return 0 }
}

export {
  ingredients, recipes, zoneMap, dragSource, dragIngId, dragOverZone,
  ingById, availableIngredients, expiredCount, expiringCount, loading,
  poolItems, freezerItems, fridgeItems, cookingItems,
  loadIngredients, addIngredient, deleteIngredient, editIngredient, markIngredient,
  onDragStart, onDragEnd, onDragOver, onDragLeave, moveToZone,
  recommendRecipes, saveCookRecord, addToShopping, realMissingCount,
}
