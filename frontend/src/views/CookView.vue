<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import {
  ingredients, recipes, loading, expiredCount, expiringCount,
  poolItems, freezerItems, fridgeItems, cookingItems,
  dragSource, dragIngId, dragOverZone,
  loadIngredients, addIngredient, deleteIngredient,
  onDragStart, onDragEnd, onDragOver, onDragLeave, moveToZone,
  recommendRecipes, saveCookRecord, addToShopping, realMissingCount,
} from '@/composables/useCook'
import { me } from '@/composables/useAuth'
import { showToast } from '@/composables/useToast'
import { isExpiring, daysLeft, CATEGORIES, CATEGORY_ICONS, guessCategory, getShelfDays } from '@/lib/constants'

const newIng = reactive({ name: '', category: '蔬菜', quantity: '1', unit: '份' })
const addDialog = reactive({ show: false })
const selectedRecipe = ref(null)

/* ---------- 拖拽处理 ---------- */
function handleDragStart(e, ing, zone) {
  onDragStart(ing, zone)
  e.dataTransfer.effectAllowed = 'move'
  e.dataTransfer.setData('text/plain', ing.id)
}

function handleDragOver(e, zone) {
  e.preventDefault()
  e.dataTransfer.dropEffect = 'move'
  onDragOver(zone)
}

function handleDragLeave(zone) {
  onDragLeave(zone)
}

function handleDrop(e, zone) {
  e.preventDefault()
  const ingId = e.dataTransfer.getData('text/plain') || dragIngId.value
  if (ingId) moveToZone(ingId, zone)
  onDragEnd()
}

function handleDragEnd() {
  onDragEnd()
}

/* ---------- 食材标签样式 ---------- */
function tagClass(ing) {
  const base = 'inline-flex items-center gap-1 rounded-lg border px-2.5 py-1 text-sm cursor-grab select-none transition-all hover:shadow-md active:cursor-grabbing'
  if (ing.status === 'expired') return base + ' bg-red-50 text-red-700 border-red-200 opacity-60'
  if (ing.status === 'used_up') return base + ' bg-gray-100 text-gray-400 border-gray-200 opacity-60'
  if (isExpiring(ing)) return base + ' bg-yellow-50 text-yellow-800 border-yellow-200'
  return base + ' bg-card text-foreground border-border hover:border-primary/50'
}

/* ---------- 添加食材 ---------- */
async function submitAdd() {
  if (!newIng.name.trim()) return
  // 自动推断分类和保质期（如果用户没手动选）
  const guessCat = guessCategory(newIng.name)
  const category = newIng.category === '蔬菜' && guessCat ? guessCat : newIng.category
  const shelf_days = getShelfDays(category)
  await addIngredient(newIng.name, category, newIng.quantity, newIng.unit, shelf_days)
  newIng.name = ''
  // 提示推断结果
  if (guessCat && guessCat !== '蔬菜') {
    showToast(`已自动归类为「${guessCat}」`)
  }
}

async function doRecommend() {
  await recommendRecipes()
}

function viewRecipe(r) { selectedRecipe.value = r }

async function doSaveCook(r) {
  await saveCookRecord(r)
  selectedRecipe.value = null
}

async function doAddToShopping(items) {
  await addToShopping(items)
}

onMounted(() => { if (me.value) loadIngredients() })
</script>

<template>
  <div class="space-y-4 md:space-y-3 md:h-full md:flex md:flex-col md:min-h-0">
    <!-- Header -->
    <div class="flex flex-wrap items-center justify-between gap-3 md:shrink-0">
      <div>
        <h1 class="text-2xl font-bold">🍳 Cook Mode</h1>
        <p class="text-sm text-muted-foreground">拖拽食材到冰箱或做菜区，AI 智能推荐菜谱</p>
      </div>
      <div class="flex items-center gap-2">
        <Badge variant="destructive">已过期 {{ expiredCount }}</Badge>
        <Badge variant="default">临期 {{ expiringCount }}</Badge>
        <Button variant="outline" size="sm" @click="loadIngredients" :disabled="loading.ingredients">
          {{ loading.ingredients ? '加载中…' : '刷新' }}
        </Button>
      </div>
    </div>

    <!-- ============ 上部分：待选池 ============ -->
    <Card
      class="border-2 md:shrink-0"
      :class="dragOverZone === 'pool' ? 'ring-2 ring-primary border-primary' : ''"
      @dragover="handleDragOver($event, 'pool')"
      @dragleave="handleDragLeave('pool')"
      @drop="handleDrop($event, 'pool')"
    >
      <CardHeader class="pb-3">
        <div class="flex items-center justify-between gap-2">
          <div>
            <CardTitle class="text-base flex items-center gap-2">
              📦 待选池
              <span class="text-xs font-normal text-muted-foreground">拖拽食材到下方冰箱或做菜区</span>
            </CardTitle>
          </div>
          <div class="flex items-center gap-2">
            <Badge variant="secondary">{{ poolItems.length }} 项</Badge>
            <Button size="sm" variant="outline" @click="addDialog.show = true">+ 添加食材</Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <!-- 快速输入 -->
        <div class="flex gap-2 mb-3">
          <Input
            v-model="newIng.name"
            placeholder="输入食材名，回车快速添加"
            class="flex-1"
            v-safe-enter="submitAdd"
          />
          <Button size="sm" @click="submitAdd" :disabled="!newIng.name.trim()">添加</Button>
        </div>

        <!-- 食材标签 -->
        <div v-if="loading.ingredients" class="text-center text-sm text-muted-foreground py-4">
          加载食材中…
        </div>
        <div v-else-if="poolItems.length === 0" class="text-center text-sm text-muted-foreground py-4">
          待选池为空，添加食材或刷新冰箱
        </div>
        <div v-else class="flex flex-wrap gap-2 md:max-h-[100px] md:overflow-y-auto">
          <div
            v-for="ing in poolItems"
            :key="ing.id"
            draggable="true"
            :class="tagClass(ing)"
            @dragstart="handleDragStart($event, ing, 'pool')"
            @dragend="handleDragEnd"
          >
            <span>{{ ing.name }}</span>
            <span class="text-xs opacity-70">{{ ing.quantity }}{{ ing.unit || '' }}</span>
            <span v-if="ing.expiry_date && isExpiring(ing)" class="text-xs text-yellow-600">剩{{ daysLeft(ing) }}天</span>
          </div>
        </div>
      </CardContent>
    </Card>

    <!-- ============ 下部分：冰箱 + 做菜区 ============ -->
    <div class="cook-bottom flex flex-col md:flex-row gap-4 md:flex-1 md:min-h-0 md:overflow-hidden">
      <!-- 左：仿真 2D 冰箱 -->
      <div class="fridge-unit flex-1">
        <!-- 温度显示屏 -->
        <div class="temp-display">
          <span><span class="label">FREEZER</span> -18°C</span>
          <span><span class="label">FRIDGE</span> 4°C</span>
        </div>

        <!-- 冰箱内部 -->
        <div class="fridge-interior">
          <!-- LED 灯条 -->
          <div class="led-bar"></div>

          <!-- 冷冻层 -->
          <div
            class="freezer-zone"
            :class="{ 'drag-active': dragOverZone === 'freezer' }"
            @dragover="handleDragOver($event, 'freezer')"
            @dragleave="handleDragLeave('freezer')"
            @drop="handleDrop($event, 'freezer')"
          >
            <div class="frost-overlay"></div>
            <div class="zone-label">
              <span>❄️ 冷冻层</span>
              <span class="count">{{ freezerItems.length }}</span>
            </div>
            <div class="zone-content">
              <div v-if="freezerItems.length === 0" class="empty-hint">
                拖拽食材到此处存放
              </div>
              <div
                v-for="ing in freezerItems"
                :key="ing.id"
                class="food-item"
                :class="{ expiring: ing.expiry_date && isExpiring(ing), expired: ing.status === 'expired' }"
                draggable="true"
                @dragstart="handleDragStart($event, ing, 'freezer')"
                @dragend="handleDragEnd"
              >
                <span class="emoji">{{ CATEGORY_ICONS[ing.category] || '📦' }}</span>
                <span>{{ ing.name }}</span>
                <span class="qty">{{ ing.quantity }}{{ ing.unit || '' }}</span>
                <span v-if="ing.expiry_date && isExpiring(ing)" class="warn">剩{{ daysLeft(ing) }}天</span>
              </div>
            </div>
          </div>

          <!-- 货架隔板 -->
          <div class="shelf"></div>

          <!-- 冷藏层 -->
          <div
            class="fridge-zone"
            :class="{ 'drag-active': dragOverZone === 'fridge' }"
            @dragover="handleDragOver($event, 'fridge')"
            @dragleave="handleDragLeave('fridge')"
            @drop="handleDrop($event, 'fridge')"
          >
            <div class="zone-label">
              <span>🥬 冷藏层</span>
              <span class="count">{{ fridgeItems.length }}</span>
            </div>
            <div class="zone-content">
              <div v-if="fridgeItems.length === 0" class="empty-hint">
                拖拽食材到此处存放
              </div>
              <div
                v-for="ing in fridgeItems"
                :key="ing.id"
                class="food-item"
                :class="{ expiring: ing.expiry_date && isExpiring(ing), expired: ing.status === 'expired' }"
                draggable="true"
                @dragstart="handleDragStart($event, ing, 'fridge')"
                @dragend="handleDragEnd"
              >
                <span class="emoji">{{ CATEGORY_ICONS[ing.category] || '📦' }}</span>
                <span>{{ ing.name }}</span>
                <span class="qty">{{ ing.quantity }}{{ ing.unit || '' }}</span>
                <span v-if="ing.expiry_date && isExpiring(ing)" class="warn">剩{{ daysLeft(ing) }}天</span>
              </div>
            </div>
          </div>
        </div>

        <div class="door-hint">↔ 拖拽食材在冷冻层和冷藏层之间移动</div>
      </div>

      <!-- 右：做菜区 -->
      <Card
        class="flex flex-col flex-1"
        :class="dragOverZone === 'cooking' ? 'ring-2 ring-primary' : ''"
        @dragover="handleDragOver($event, 'cooking')"
        @dragleave="handleDragLeave('cooking')"
        @drop="handleDrop($event, 'cooking')"
      >
        <CardHeader class="pb-3 shrink-0">
          <div class="flex items-center justify-between gap-2">
            <div>
              <CardTitle class="text-base">🍳 做菜区</CardTitle>
              <CardDescription class="text-xs">拖入食材后点击生成菜谱</CardDescription>
            </div>
            <Badge variant="default">{{ cookingItems.length }} 项</Badge>
          </div>
        </CardHeader>
        <CardContent class="space-y-4 flex-1 flex flex-col min-h-0">
          <!-- 食材标签 -->
          <div
            class="min-h-[80px] rounded-lg border-2 border-dashed p-3 transition-all shrink-0"
            :class="dragOverZone === 'cooking' ? 'border-primary bg-primary/5' : 'border-border bg-muted/20'"
          >
            <div v-if="cookingItems.length === 0" class="text-center text-sm text-muted-foreground py-4">
              拖拽食材到此区域
            </div>
            <div v-else class="flex flex-wrap gap-2">
              <div
                v-for="ing in cookingItems"
                :key="ing.id"
                draggable="true"
                :class="tagClass(ing)"
                @dragstart="handleDragStart($event, ing, 'cooking')"
                @dragend="handleDragEnd"
              >
                <span>{{ ing.name }}</span>
                <span class="text-xs opacity-70">{{ ing.quantity }}{{ ing.unit || '' }}</span>
              </div>
            </div>
          </div>

          <!-- 生成菜谱按钮 -->
          <Button
            class="w-full shrink-0"
            size="lg"
            :disabled="cookingItems.length === 0 || loading.recipes"
            @click="doRecommend"
          >
            {{ loading.recipes ? '🤖 AI 生成中…' : `🤖 生成菜谱（${cookingItems.length} 种食材）` }}
          </Button>

          <!-- 菜谱结果 -->
          <div v-if="loading.recipes" class="rounded-lg border bg-muted/30 py-8 text-center text-sm text-muted-foreground shrink-0">
            AI 正在生成菜谱…
          </div>
          <div v-else-if="recipes.length === 0" class="rounded-lg border bg-muted/30 py-6 text-center text-sm text-muted-foreground shrink-0">
            点击「生成菜谱」获取 AI 推荐
          </div>
          <div v-else class="space-y-2 flex-1 min-h-0 overflow-y-auto">
            <Card v-for="r in recipes" :key="r.cache_id || r.name" class="shadow-sm">
              <CardContent class="p-3 space-y-2">
                <div class="flex items-start justify-between gap-2">
                  <div class="min-w-0">
                    <p class="font-semibold text-sm truncate">{{ r.name }}</p>
                    <p class="text-xs text-muted-foreground">
                      {{ r.estimated_cost || '-' }} · {{ r.cooking_time || '-' }}
                    </p>
                  </div>
                  <Button size="xs" variant="ghost" @click="viewRecipe(r)">详情</Button>
                </div>
                <div class="flex flex-wrap gap-1">
                  <Badge
                    v-for="ing in (r.matched_ingredients || [])"
                    :key="'m' + ing"
                    class="bg-green-100 text-green-700 border-green-200 text-xs"
                  >✓ {{ ing }}</Badge>
                  <Badge
                    v-for="ing in (r.missing_ingredients || [])"
                    :key="'s' + ing"
                    class="bg-orange-100 text-orange-700 border-orange-200 text-xs"
                  >✗ {{ ing }}</Badge>
                </div>
                <div class="flex gap-2">
                  <Button size="xs" @click="doSaveCook(r)">记录做饭</Button>
                  <Button
                    size="xs"
                    variant="outline"
                    :disabled="realMissingCount(r) === 0"
                    @click="doAddToShopping(r.missing_ingredients || [])"
                  >同步购物单</Button>
                </div>
              </CardContent>
            </Card>
          </div>
        </CardContent>
      </Card>
    </div>

    <!-- 添加食材 Dialog -->
    <Dialog :open="addDialog.show" @update:open="v => addDialog.show = v">
      <DialogContent class="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>快速添加食材</DialogTitle>
          <DialogDescription>添加后食材将进入待选池</DialogDescription>
        </DialogHeader>
        <div class="space-y-4 py-2">
          <div class="space-y-2">
            <Label for="ck-name">名称</Label>
            <Input id="ck-name" v-model="newIng.name" placeholder="如：番茄" v-safe-enter="submitAdd" />
          </div>
          <div class="grid grid-cols-2 gap-3">
            <div class="space-y-2">
              <Label>分类</Label>
              <Select v-model="newIng.category">
                <SelectTrigger class="w-full"><SelectValue placeholder="选择分类" /></SelectTrigger>
                <SelectContent>
                  <SelectItem v-for="c in CATEGORIES" :key="c" :value="c">{{ c }}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div class="space-y-2">
              <Label for="ck-qty">数量</Label>
              <Input id="ck-qty" v-model="newIng.quantity" placeholder="如：2" v-safe-enter="submitAdd" />
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" @click="addDialog.show = false">取消</Button>
          <Button @click="submitAdd">添加</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <!-- 菜谱详情 Dialog -->
    <Dialog :open="!!selectedRecipe" @update:open="v => { if (!v) selectedRecipe = null }">
      <DialogContent class="sm:max-w-lg">
        <DialogHeader v-if="selectedRecipe">
          <DialogTitle>{{ selectedRecipe.name }}</DialogTitle>
          <DialogDescription>
            预估 {{ selectedRecipe.estimated_cost || '-' }} · 用时 {{ selectedRecipe.cooking_time || '-' }}
          </DialogDescription>
        </DialogHeader>
        <div v-if="selectedRecipe" class="space-y-4 py-2 max-h-[60vh] overflow-y-auto">
          <div class="flex flex-wrap gap-1">
            <Badge
              v-for="ing in (selectedRecipe.matched_ingredients || [])"
              :key="'m' + ing"
              class="bg-green-100 text-green-700 border-green-200"
            >✓ {{ ing }}</Badge>
            <Badge
              v-for="ing in (selectedRecipe.missing_ingredients || [])"
              :key="'s' + ing"
              class="bg-orange-100 text-orange-700 border-orange-200"
            >✗ {{ ing }}</Badge>
          </div>
          <div>
            <p class="text-xs font-medium text-muted-foreground mb-2">步骤</p>
            <ol class="text-sm space-y-1.5 list-decimal list-inside">
              <li v-for="(s, i) in (selectedRecipe.steps || [])" :key="i">{{ s }}</li>
            </ol>
            <p v-if="(selectedRecipe.steps || []).length === 0" class="text-sm text-muted-foreground">暂无步骤信息</p>
          </div>
        </div>
        <DialogFooter v-if="selectedRecipe">
          <Button
            variant="outline"
            :disabled="realMissingCount(selectedRecipe) === 0"
            @click="doAddToShopping(selectedRecipe.missing_ingredients || [])"
          >同步购物单</Button>
          <Button @click="doSaveCook(selectedRecipe)">记录为今日做饭</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>

<style scoped>
/* ===== 仿真 2D 冰箱 ===== */
.fridge-unit {
  background: linear-gradient(135deg, #e8e8e8 0%, #c0c0c0 100%);
  border-radius: 16px;
  border: 2px solid #999;
  box-shadow: 0 8px 24px rgba(0,0,0,0.12), inset 0 1px 0 rgba(255,255,255,0.5);
  padding: 12px;
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
:root[data-theme="dark"] .fridge-unit,
.dark .fridge-unit {
  background: linear-gradient(135deg, #3a3a3a 0%, #2a2a2a 100%);
  border-color: #555;
}

/* 温度显示屏 */
.temp-display {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #1a1a1a;
  color: #4ade80;
  font-family: "Courier New", monospace;
  font-size: 11px;
  padding: 4px 10px;
  border-radius: 6px;
  margin-bottom: 8px;
  font-weight: bold;
  letter-spacing: 0.05em;
  flex-shrink: 0;
}
.temp-display .label { color: #888; font-size: 9px; margin-right: 2px; }

/* 冰箱内部 */
.fridge-interior {
  background: #f5f5f0;
  border-radius: 8px;
  overflow: hidden;
  position: relative;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}
:root[data-theme="dark"] .fridge-interior,
.dark .fridge-interior { background: #2a2a28; }

/* LED 灯条 */
.led-bar {
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 3px;
  background: linear-gradient(90deg, transparent, #fffde0, transparent);
  box-shadow: 0 0 8px #fffde0, 0 2px 6px rgba(255,253,224,0.4);
  z-index: 2;
}

/* 冷冻层 */
.freezer-zone {
  background: linear-gradient(180deg, #e8f4ff 0%, #d0e8ff 100%);
  padding: 10px 10px;
  position: relative;
  transition: all 0.25s;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}
:root[data-theme="dark"] .freezer-zone,
.dark .freezer-zone {
  background: linear-gradient(180deg, #1a2a3a 0%, #0d1a2a 100%);
}
.freezer-zone.drag-active {
  box-shadow: inset 0 0 0 2px var(--primary, #6366f1);
  background: linear-gradient(180deg, #c0d8ff 0%, #a0c8ff 100%);
}

/* 货架隔板 */
.shelf {
  height: 4px;
  background: linear-gradient(180deg, #cdcdcd 0%, #999 50%, #cdcdcd 100%);
  box-shadow: 0 2px 4px rgba(0,0,0,0.15);
  border-radius: 1px;
  flex-shrink: 0;
}
:root[data-theme="dark"] .shelf,
.dark .shelf {
  background: linear-gradient(180deg, #555 0%, #333 50%, #555 100%);
}

/* 冷藏层 */
.fridge-zone {
  background: linear-gradient(180deg, #f8fff8 0%, #e8ffe8 100%);
  padding: 10px 10px;
  position: relative;
  transition: all 0.25s;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}
:root[data-theme="dark"] .fridge-zone,
.dark .fridge-zone {
  background: linear-gradient(180deg, #1a2a1a 0%, #0d1a0d 100%);
}
.fridge-zone.drag-active {
  box-shadow: inset 0 0 0 2px var(--primary, #6366f1);
  background: linear-gradient(180deg, #d0ffd0 0%, #b0ffb0 100%);
}

/* 霜雾效果 */
.frost-overlay {
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  background:
    radial-gradient(ellipse at 20% 30%, rgba(255,255,255,0.3), transparent 50%),
    radial-gradient(ellipse at 70% 60%, rgba(255,255,255,0.2), transparent 50%);
  pointer-events: none;
  z-index: 1;
}

/* 区域标签 */
.zone-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: #666;
  font-weight: 600;
  margin-bottom: 6px;
  position: relative;
  z-index: 2;
  flex-shrink: 0;
}
:root[data-theme="dark"] .zone-label,
.dark .zone-label { color: #999; }
.zone-label .count {
  background: rgba(99,102,241,0.15);
  color: #6366f1;
  padding: 1px 6px;
  border-radius: 8px;
  font-size: 10px;
}

.zone-content {
  position: relative;
  z-index: 2;
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}

.empty-hint {
  text-align: center;
  font-size: 11px;
  color: #aaa;
  padding: 20px 0;
}

/* 食材物品 */
.food-item {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  background: rgba(255,255,255,0.85);
  border: 1px solid #ddd;
  border-radius: 6px;
  padding: 3px 8px;
  font-size: 12px;
  margin: 2px;
  cursor: grab;
  transition: all 0.15s;
  box-shadow: 0 1px 2px rgba(0,0,0,0.08);
}
:root[data-theme="dark"] .food-item,
.dark .food-item {
  background: rgba(50,50,50,0.85);
  border-color: #555;
  color: #ddd;
}
.food-item:hover {
  transform: translateY(-1px);
  box-shadow: 0 3px 8px rgba(0,0,0,0.15);
}
.food-item.expiring {
  border-color: #fbbf24;
  background: rgba(254,243,199,0.9);
}
.food-item.expired {
  border-color: #ef4444;
  opacity: 0.5;
  text-decoration: line-through;
}
.food-item .emoji { font-size: 13px; }
.food-item .qty { font-size: 10px; opacity: 0.6; }
.food-item .warn { font-size: 10px; color: #d97706; }

/* 门把手提示 */
.door-hint {
  text-align: center;
  font-size: 10px;
  color: #888;
  margin-top: 8px;
  padding: 4px;
  background: rgba(0,0,0,0.05);
  border-radius: 4px;
  flex-shrink: 0;
}
:root[data-theme="dark"] .door-hint,
.dark .door-hint { background: rgba(255,255,255,0.05); color: #999; }

/* 桌面端：flex-row + 强制等高（min-height 由父级 flex 分配） */
@media (min-width: 768px) {
  .cook-bottom {
    flex-direction: row !important;
    align-items: stretch !important;
  }
  .cook-bottom > * {
    align-self: stretch !important;
    min-height: 0;
  }
}
</style>
