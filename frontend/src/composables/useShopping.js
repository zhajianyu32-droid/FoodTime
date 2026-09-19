import { ref } from 'vue'
import { api } from './useApi'
import { me } from './useAuth'
import { showToast } from './useToast'

const shoppingItems = ref([])
const shoppingPendingCount = ref(0)
const shoppingCheckedCount = ref(0)
const loading = ref(false)

async function loadShopping() {
  if (!me.value) return
  loading.value = true
  try {
    const uid = me.value.user_id || me.value.id
    const r = await api(`/shopping/${uid}?page_size=100`)
    const items = r.items || r || []
    shoppingItems.value = items
    shoppingPendingCount.value = items.filter(s => !s.checked).length
    shoppingCheckedCount.value = items.filter(s => s.checked).length
  } catch (e) {
    shoppingItems.value = []
  }
  finally { loading.value = false }
}

async function addShoppingItem(name, category, quantity) {
  if (!me.value || !name.trim()) return
  try {
    const uid = me.value.user_id || me.value.id
    const item = await api('/shopping', {
      method: 'POST',
      body: { user_id: uid, name: name.trim(), category: category || '其他', quantity: quantity || '' }
    })
    shoppingItems.value.unshift(item)
    shoppingPendingCount.value++
    showToast('已加入购物单 ✓')
  } catch (e) { showToast(e.message, 'error') }
}

async function toggleShopItem(item) {
  try {
    const next = !item.checked
    const updated = await api(`/shopping/${item.id}`, { method: 'PUT', body: { checked: next } })
    Object.assign(item, updated)
    if (next) { shoppingCheckedCount.value++; shoppingPendingCount.value-- }
    else { shoppingCheckedCount.value--; shoppingPendingCount.value++ }
  } catch (e) { showToast(e.message, 'error') }
}

async function deleteShopItem(item) {
  try {
    await api(`/shopping/${item.id}`, { method: 'DELETE' })
    shoppingItems.value = shoppingItems.value.filter(x => x.id !== item.id)
    if (item.checked) shoppingCheckedCount.value--
    else shoppingPendingCount.value--
    showToast('已移除')
  } catch (e) { showToast(e.message, 'error') }
}

async function clearCheckedShopping() {
  const checked = shoppingItems.value.filter(s => s.checked)
  if (checked.length === 0) return
  try {
    for (const it of checked) { await api(`/shopping/${it.id}`, { method: 'DELETE' }) }
    const ids = new Set(checked.map(x => x.id))
    shoppingItems.value = shoppingItems.value.filter(x => !ids.has(x.id))
    shoppingCheckedCount.value = 0
    showToast('已清空已勾选')
  } catch (e) { showToast(e.message, 'error') }
}

async function moveToIngredients(item) {
  try {
    const uid = me.value.user_id || me.value.id
    await api('/ingredients', {
      method: 'POST',
      body: { user_id: uid, name: item.name, category: item.category || '其他', quantity: item.quantity || '1' }
    })
    await api(`/shopping/${item.id}`, { method: 'DELETE' })
    shoppingItems.value = shoppingItems.value.filter(x => x.id !== item.id)
    if (item.checked) shoppingCheckedCount.value--
    else shoppingPendingCount.value--
    showToast(`「${item.name}」已入库冰箱 ✓`)
  } catch (e) { showToast(e.message, 'error') }
}

async function bulkMoveCheckedToIngredients() {
  const items = shoppingItems.value.filter(s => s.checked)
  if (items.length === 0) return
  loading.value = true
  let ok = 0
  for (const it of items) {
    try {
      const uid = me.value.user_id || me.value.id
      await api('/ingredients', {
        method: 'POST',
        body: { user_id: uid, name: it.name, category: it.category || '其他', quantity: it.quantity || '1' }
      })
      await api(`/shopping/${it.id}`, { method: 'DELETE' })
      ok++
    } catch (e) {}
  }
  loading.value = false
  const ids = new Set(items.map(x => x.id))
  shoppingItems.value = shoppingItems.value.filter(x => !ids.has(x.id))
  shoppingCheckedCount.value = 0
  showToast(`成功入库 ${ok}/${items.length} 项 ✓`)
}

export {
  shoppingItems, shoppingPendingCount, shoppingCheckedCount, loading,
  loadShopping, addShoppingItem, toggleShopItem, deleteShopItem,
  clearCheckedShopping, moveToIngredients, bulkMoveCheckedToIngredients,
}
