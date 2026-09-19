<script setup>
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { ingredients, loadIngredients, addIngredient, deleteIngredient, editIngredient, markIngredient, loading, expiredCount, expiringCount } from '@/composables/useCook'
import { me } from '@/composables/useAuth'
import { showToast } from '@/composables/useToast'
import { CATEGORIES, isExpiring, daysLeft, getShelfDays, computeExpiryDate, guessCategory } from '@/lib/constants'

const ingForm = reactive({ name: '', category: '蔬菜', quantity: '', shelf_days: null, expiry_date: '' })
const ingFilter = reactive({ status: 'all', category: 'all', search: '' })
const editDialog = reactive({ show: false, id: null, name: '', category: '蔬菜', quantity: '', shelf_days: null, expiry_date: '' })
const deleteDialog = reactive({ show: false, item: null })

// 添加表单中，分类变更时自动填入默认保质期（仅当用户未手动修改过）
const shelfDaysTouched = ref(false)
watch(() => ingForm.category, (cat) => {
  if (!shelfDaysTouched.value) {
    ingForm.shelf_days = getShelfDays(cat)
  }
})

const filteredIngredients = computed(() => {
  let list = ingredients.value
  const s = ingFilter.status
  if (s && s !== 'all') {
    if (s === 'available') list = list.filter(i => i.status !== 'expired' && i.status !== 'used_up')
    else if (s === 'expiring') list = list.filter(i => i.status !== 'expired' && i.status !== 'used_up' && isExpiring(i))
    else list = list.filter(i => i.status === s)
  }
  if (ingFilter.category && ingFilter.category !== 'all') list = list.filter(i => i.category === ingFilter.category)
  if (ingFilter.search) {
    const q = ingFilter.search.trim().toLowerCase()
    list = list.filter(i => (i.name || '').toLowerCase().includes(q))
  }
  return list
})

function displayStatus(ing) {
  if (ing.status === 'expired' || ing.status === 'used_up') return ing.status
  return isExpiring(ing) ? 'expiring' : 'fresh'
}

function submitAdd() {
  if (!ingForm.name.trim()) { showToast('请输入食材名称', 'error'); return }
  // 自动推断分类（如果用户没手动改默认的"蔬菜"）
  const guessCat = guessCategory(ingForm.name)
  const category = ingForm.category === '蔬菜' && guessCat ? guessCat : ingForm.category
  const shelf_days = ingForm.shelf_days || getShelfDays(category)
  addIngredient(ingForm.name, category, ingForm.quantity || '1', '份', shelf_days)
  ingForm.name = ''; ingForm.quantity = ''; ingForm.shelf_days = null; ingForm.expiry_date = ''
  shelfDaysTouched.value = false
  if (guessCat && category !== '蔬菜') showToast(`已自动归类为「${category}」`)
}

function openEdit(ing) {
  Object.assign(editDialog, { show: true, id: ing.id, name: ing.name, category: ing.category || '蔬菜', quantity: ing.quantity || '', shelf_days: ing.shelf_days ?? null, expiry_date: ing.expiry_date || '' })
}

async function submitEdit() {
  if (!editDialog.name.trim()) return
  const patch = { name: editDialog.name.trim(), category: editDialog.category, quantity: editDialog.quantity }
  if (editDialog.shelf_days !== null && editDialog.shelf_days !== undefined) patch.shelf_days = editDialog.shelf_days
  if (editDialog.expiry_date) patch.expiry_date = editDialog.expiry_date
  await editIngredient({ id: editDialog.id }, patch)
  editDialog.show = false
}

function confirmDelete(ing) {
  deleteDialog.item = ing
  deleteDialog.show = true
}

async function doDelete() {
  await deleteIngredient(deleteDialog.item)
  deleteDialog.show = false
}

async function doMark(ing, status) {
  await markIngredient(ing, status)
}

function statusVariant(status) {
  return { expired: 'destructive', used_up: 'secondary', expiring: 'default', fresh: 'default' }[status] || 'default'
}
function statusLabel(status) {
  return { expired: '已过期', used_up: '已用完', expiring: '临期', fresh: '新鲜' }[status] || status || '新鲜'
}

onMounted(() => { if (me.value) loadIngredients() })
</script>

<template>
  <div class="min-h-screen bg-background p-4 md:p-8">
    <div class="max-w-5xl mx-auto space-y-6">
      <!-- Header -->
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 class="text-2xl font-bold">食材管理</h1>
          <p class="text-sm text-muted-foreground">管理冰箱里的食材，及时处理临期与过期</p>
        </div>
        <div class="flex items-center gap-2">
          <Badge variant="destructive">已过期 {{ expiredCount }}</Badge>
          <Badge variant="default">临期 {{ expiringCount }}</Badge>
          <Button variant="outline" size="sm" @click="loadIngredients" :disabled="loading.ingredients">
            {{ loading.ingredients ? '加载中…' : '刷新' }}
          </Button>
        </div>
      </div>

      <!-- Add Form -->
      <Card>
        <CardHeader>
          <CardTitle class="text-lg">添加食材</CardTitle>
        </CardHeader>
        <CardContent>
          <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-6">
            <div class="space-y-2 lg:col-span-2">
              <Label for="ing-name">名称</Label>
              <Input id="ing-name" v-model="ingForm.name" placeholder="如：番茄" v-safe-enter="submitAdd" />
            </div>
            <div class="space-y-2">
              <Label>分类</Label>
              <Select v-model="ingForm.category">
                <SelectTrigger class="w-full"><SelectValue placeholder="选择分类" /></SelectTrigger>
                <SelectContent>
                  <SelectItem v-for="c in CATEGORIES" :key="c" :value="c">{{ c }}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div class="space-y-2">
              <Label for="ing-qty">数量</Label>
              <Input id="ing-qty" v-model="ingForm.quantity" placeholder="如：2" v-safe-enter="submitAdd" />
            </div>
            <div class="space-y-2">
              <Label for="ing-shelf">保质期（天）</Label>
              <Input
                id="ing-shelf"
                type="number" min="1" max="3650"
                v-model.number="ingForm.shelf_days"
                :placeholder="getShelfDays(ingForm.category) + '（默认）'"
                @input="shelfDaysTouched = true"
                v-safe-enter="submitAdd"
              />
            </div>
            <div class="space-y-2">
              <Label for="ing-exp">过期日期（可选）</Label>
              <Input id="ing-exp" type="date" v-model="ingForm.expiry_date" />
            </div>
          </div>
          <div class="mt-4 flex justify-end">
            <Button @click="submitAdd" :disabled="loading.ingredients">添加</Button>
          </div>
        </CardContent>
      </Card>

      <!-- Filter + Table -->
      <Card>
        <CardHeader>
          <CardTitle class="text-lg">食材清单</CardTitle>
        </CardHeader>
        <CardContent class="space-y-4">
          <!-- Filter bar -->
          <div class="grid gap-3 sm:grid-cols-3">
            <div class="space-y-1.5">
              <Label class="text-xs text-muted-foreground">状态</Label>
              <Select v-model="ingFilter.status">
                <SelectTrigger class="w-full"><SelectValue placeholder="全部状态" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">全部</SelectItem>
                  <SelectItem value="available">可用</SelectItem>
                  <SelectItem value="expiring">临期</SelectItem>
                  <SelectItem value="expired">已过期</SelectItem>
                  <SelectItem value="used_up">已用完</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div class="space-y-1.5">
              <Label class="text-xs text-muted-foreground">分类</Label>
              <Select v-model="ingFilter.category">
                <SelectTrigger class="w-full"><SelectValue placeholder="全部分类" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">全部</SelectItem>
                  <SelectItem v-for="c in CATEGORIES" :key="c" :value="c">{{ c }}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div class="space-y-1.5">
              <Label class="text-xs text-muted-foreground" for="ing-search">搜索</Label>
              <Input id="ing-search" v-model="ingFilter.search" placeholder="按名称搜索" />
            </div>
          </div>

          <!-- Table -->
          <div class="rounded-lg border overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>名称</TableHead>
                  <TableHead>分类</TableHead>
                  <TableHead class="text-right">数量</TableHead>
                  <TableHead>保质期</TableHead>
                  <TableHead>过期日</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead class="text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow v-if="filteredIngredients.length === 0">
                  <TableCell :col-span="7" class="text-center text-sm text-muted-foreground py-8">
                    暂无符合条件的食材
                  </TableCell>
                </TableRow>
                <TableRow v-for="ing in filteredIngredients" :key="ing.id">
                  <TableCell class="font-medium">{{ ing.name }}</TableCell>
                  <TableCell>{{ ing.category || '-' }}</TableCell>
                  <TableCell class="text-right">{{ ing.quantity }}{{ ing.unit || '' }}</TableCell>
                  <TableCell>
                    <span class="text-sm">
                      {{ ing.shelf_days ? ing.shelf_days + ' 天' : (getShelfDays(ing.category) + ' 天（默认）') }}
                    </span>
                  </TableCell>
                  <TableCell>
                    <div class="flex flex-col gap-1">
                      <span class="text-sm">{{ computeExpiryDate(ing) || '—' }}</span>
                      <Badge
                        v-if="computeExpiryDate(ing)"
                        :variant="daysLeft(ing) < 0 ? 'destructive' : (daysLeft(ing) <= 3 ? 'default' : 'secondary')"
                        class="w-fit"
                      >
                        {{ daysLeft(ing) < 0 ? `已过期 ${Math.abs(daysLeft(ing))} 天` : `剩 ${daysLeft(ing)} 天` }}
                      </Badge>
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge :variant="statusVariant(displayStatus(ing))">
                      {{ statusLabel(displayStatus(ing)) }}
                    </Badge>
                  </TableCell>
                  <TableCell class="text-right">
                    <div class="flex flex-wrap justify-end gap-1">
                      <Button
                        v-if="ing.status !== 'expired' && ing.status !== 'used_up'"
                        size="sm" variant="ghost"
                        @click="doMark(ing, 'expired')"
                      >标过期</Button>
                      <Button
                        v-if="ing.status !== 'used_up'"
                        size="sm" variant="ghost"
                        @click="doMark(ing, 'used_up')"
                      >标用完</Button>
                      <Button size="sm" variant="outline" @click="openEdit(ing)">编辑</Button>
                      <Button size="sm" variant="ghost" class="text-destructive hover:text-destructive" @click="confirmDelete(ing)">删除</Button>
                    </div>
                  </TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      <!-- Edit Dialog -->
      <Dialog :open="editDialog.show" @update:open="v => editDialog.show = v">
        <DialogContent class="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>编辑食材</DialogTitle>
            <DialogDescription>修改食材的名称、分类与数量。</DialogDescription>
          </DialogHeader>
          <div class="space-y-4 py-2">
            <div class="space-y-2">
              <Label for="edit-name">名称</Label>
              <Input id="edit-name" v-model="editDialog.name" />
            </div>
            <div class="space-y-2">
              <Label>分类</Label>
              <Select v-model="editDialog.category">
                <SelectTrigger class="w-full"><SelectValue placeholder="选择分类" /></SelectTrigger>
                <SelectContent>
                  <SelectItem v-for="c in CATEGORIES" :key="c" :value="c">{{ c }}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div class="space-y-2">
              <Label for="edit-qty">数量</Label>
              <Input id="edit-qty" v-model="editDialog.quantity" />
            </div>
            <div class="space-y-2">
              <Label for="edit-shelf">保质期（天）</Label>
              <Input
                id="edit-shelf"
                type="number" min="1" max="3650"
                v-model.number="editDialog.shelf_days"
                :placeholder="getShelfDays(editDialog.category) + '（分类默认）'"
              />
            </div>
            <div class="space-y-2">
              <Label for="edit-exp">过期日期（可选，留空则按保质期自动计算）</Label>
              <Input id="edit-exp" type="date" v-model="editDialog.expiry_date" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" @click="editDialog.show = false">取消</Button>
            <Button @click="submitEdit">保存</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <!-- Delete Dialog -->
      <Dialog :open="deleteDialog.show" @update:open="v => deleteDialog.show = v">
        <DialogContent class="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>删除食材</DialogTitle>
            <DialogDescription>确定要删除「{{ deleteDialog.item?.name }}」吗？此操作不可撤销。</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" @click="deleteDialog.show = false">取消</Button>
            <Button variant="destructive" @click="doDelete">确认删除</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  </div>
</template>
