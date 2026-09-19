<script setup>
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Checkbox } from '@/components/ui/checkbox'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import {
  shoppingItems, shoppingPendingCount, shoppingCheckedCount,
  loadShopping, addShoppingItem, toggleShopItem, deleteShopItem,
  clearCheckedShopping, moveToIngredients, bulkMoveCheckedToIngredients,
} from '@/composables/useShopping'
import { loadIngredients } from '@/composables/useCook'
import { me } from '@/composables/useAuth'
import { showToast } from '@/composables/useToast'
import { CATEGORIES, CATEGORY_ICONS } from '@/lib/constants'

/* ---------- 状态 ---------- */
const newShop = reactive({ name: '', category: '其他', quantity: '' })
const shopFilter = ref('all')
const adding = ref(false)
const addInputRef = ref(null)

/* ---------- 过滤 ---------- */
const filteredShopping = computed(() => {
  if (shopFilter.value === 'pending') return shoppingItems.value.filter(s => !s.checked)
  if (shopFilter.value === 'checked') return shoppingItems.value.filter(s => s.checked)
  return shoppingItems.value
})

/* ---------- 进度 ---------- */
const totalCount = computed(() => shoppingPendingCount.value + shoppingCheckedCount.value)
const progressPercent = computed(() => {
  if (totalCount.value === 0) return 0
  return Math.round((shoppingCheckedCount.value / totalCount.value) * 100)
})

/* ---------- 添加 ---------- */
async function submitAdd() {
  if (!newShop.name.trim()) { showToast('请输入购买项名称', 'error'); return }
  adding.value = true
  await addShoppingItem(newShop.name, newShop.category, newShop.quantity)
  newShop.name = ''; newShop.quantity = ''
  adding.value = false
  // 重新聚焦输入框，方便连续添加
  await nextTick()
  const el = addInputRef.value?.$el || addInputRef.value
  el?.focus?.()
}

/* ---------- 单项操作 ---------- */
async function onToggle(item) {
  await toggleShopItem(item)
}

async function doMoveToIngredients(item) {
  await moveToIngredients(item)
  await loadIngredients()
}

async function doBulkMove() {
  if (!shoppingCheckedCount) { showToast('没有已勾选的项', 'error'); return }
  await bulkMoveCheckedToIngredients()
  await loadIngredients()
}

async function doClearChecked() {
  await clearCheckedShopping()
}

async function doDelete(item) {
  await deleteShopItem(item)
}

onMounted(() => { if (me.value) loadShopping() })
</script>

<template>
  <div class="max-w-3xl mx-auto space-y-5">
    <!-- Header -->
    <div class="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 class="text-2xl font-bold tracking-tight">🛒 购物清单</h1>
        <p class="text-sm text-muted-foreground mt-0.5">勾选已购买的食材，一键移入冰箱</p>
      </div>
      <div class="flex items-center gap-2">
        <Button variant="ghost" size="sm" @click="loadShopping" :disabled="false">
          <span class="text-base">↻</span>
        </Button>
      </div>
    </div>

    <!-- 进度卡 -->
    <div class="rounded-xl border bg-card p-4 space-y-3">
      <div class="flex items-center justify-between">
        <div class="flex items-baseline gap-2">
          <span class="text-3xl font-bold tabular-nums">{{ shoppingCheckedCount }}</span>
          <span class="text-sm text-muted-foreground">/ {{ totalCount }} 已购买</span>
        </div>
        <div class="flex items-center gap-1.5">
          <Badge v-if="shoppingPendingCount > 0" variant="secondary" class="text-xs">
            还差 {{ shoppingPendingCount }} 项
          </Badge>
          <Badge v-else-if="totalCount > 0" class="bg-green-600 text-white text-xs">
            ✓ 全部完成
          </Badge>
        </div>
      </div>
      <Progress :model-value="progressPercent" class="h-2" />
      <div class="flex items-center justify-end gap-2 pt-0.5">
        <Button
          size="sm" variant="ghost"
          :disabled="!shoppingCheckedCount"
          @click="doClearChecked"
          class="text-muted-foreground hover:text-destructive"
        >清空已勾选</Button>
        <Button
          size="sm" variant="outline"
          :disabled="!shoppingCheckedCount"
          @click="doBulkMove"
        >📥 全部移入冰箱</Button>
      </div>
    </div>

    <!-- 筛选 -->
    <Tabs v-model="shopFilter" class="w-full">
      <TabsList class="w-full">
        <TabsTrigger value="all" class="flex-1">全部 {{ totalCount }}</TabsTrigger>
        <TabsTrigger value="pending" class="flex-1">待购买 {{ shoppingPendingCount }}</TabsTrigger>
        <TabsTrigger value="checked" class="flex-1">已勾选 {{ shoppingCheckedCount }}</TabsTrigger>
      </TabsList>
    </Tabs>

    <!-- 笔记本式购物清单 -->
    <div class="rounded-xl border bg-card overflow-hidden shadow-sm">
      <!-- 横线笔记本背景 -->
      <div class="relative">
        <!-- 笔记本左侧装订线 -->
        <div class="absolute left-0 top-0 bottom-0 w-1 bg-red-200/60 dark:bg-red-900/30"></div>

        <!-- 空状态 -->
        <div v-if="filteredShopping.length === 0 && !adding" class="py-16 text-center">
          <div class="text-4xl mb-2 opacity-30">📝</div>
          <p class="text-sm text-muted-foreground">
            {{ shopFilter === 'checked' ? '还没有勾选任何项' : '在下方输入框添加第一项' }}
          </p>
        </div>

        <!-- 列表行 -->
        <div
          v-for="(item, idx) in filteredShopping"
          :key="item.id"
          class="group relative flex items-center gap-3 px-4 py-3 transition-colors hover:bg-muted/30"
          :class="[
            item.checked ? 'bg-muted/20' : '',
            idx !== filteredShopping.length - 1 ? 'border-b border-muted/40' : '',
          ]"
        >
          <!-- 勾选框 -->
          <Checkbox
            :model-value="!!item.checked"
            @update:model-value="onToggle(item)"
            class="shrink-0"
          />

          <!-- 分类图标 -->
          <span class="shrink-0 text-base opacity-50 w-5 text-center">
            {{ CATEGORY_ICONS?.[item.category] || '🛒' }}
          </span>

          <!-- 名称 + 数量 -->
          <div class="flex-1 min-w-0 flex items-baseline gap-2">
            <span
              class="truncate transition-all"
              :class="item.checked
                ? 'line-through text-muted-foreground'
                : 'font-medium'"
            >{{ item.name }}</span>
            <span v-if="item.quantity" class="text-xs text-muted-foreground shrink-0">
              {{ item.quantity }}{{ item.unit || '' }}
            </span>
          </div>

          <!-- 分类标签 -->
          <Badge v-if="item.category && item.category !== '其他'" variant="outline" class="shrink-0 text-xs font-normal">
            {{ item.category }}
          </Badge>

          <!-- 悬浮操作 -->
          <div class="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
            <Button
              size="sm" variant="ghost"
              class="h-7 px-2 text-xs"
              @click="doMoveToIngredients(item)"
              title="移入冰箱"
            >📥</Button>
            <Button
              size="sm" variant="ghost"
              class="h-7 px-2 text-xs hover:text-destructive"
              @click="doDelete(item)"
              title="删除"
            >✕</Button>
          </div>
        </div>

        <!-- 添加行（始终显示在底部） -->
        <div
          v-if="shopFilter !== 'checked'"
          class="flex items-center gap-3 px-4 py-3 border-b border-muted/40 bg-muted/10"
          :class="{ 'border-t-2 border-t-primary/20': filteredShopping.length > 0 }"
        >
          <!-- 占位勾选框 -->
          <div class="w-4 shrink-0"></div>

          <!-- 分类图标 -->
          <span class="shrink-0 text-base opacity-30 w-5 text-center">＋</span>

          <!-- 快速输入 -->
          <Input
            ref="addInputRef"
            v-model="newShop.name"
            placeholder="输入食材名，回车添加…"
            class="flex-1 border-0 shadow-none bg-transparent focus-visible:ring-0 px-0"
            v-safe-enter="submitAdd"
          />

          <!-- 分类选择（紧凑） -->
          <Select v-model="newShop.category">
            <SelectTrigger class="w-[90px] h-8 text-xs border-0 bg-muted/50">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem v-for="c in CATEGORIES" :key="c" :value="c">{{ c }}</SelectItem>
            </SelectContent>
          </Select>

          <!-- 数量 -->
          <Input
            v-model="newShop.quantity"
            placeholder="数量"
            class="w-16 h-8 text-xs"
            v-safe-enter="submitAdd"
          />

          <!-- 添加按钮 -->
          <Button
            size="sm"
            class="h-8 shrink-0"
            :disabled="!newShop.name.trim() || adding"
            @click="submitAdd"
          >添加</Button>
        </div>
      </div>
    </div>

    <!-- 底部提示 -->
    <div v-if="totalCount > 0" class="flex items-center justify-center gap-2 text-xs text-muted-foreground">
      <span>💡 勾选食材后点击「全部移入冰箱」可批量入库</span>
    </div>
  </div>
</template>
