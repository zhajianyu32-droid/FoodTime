<script setup>
import { onMounted, computed } from 'vue'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { stats, diaryList, diaryFilter, filteredDiary, recentDiary, prefWeights, heatmapDays, currentYearMonth, loadStats, loadHeatmap, loadPrefWeights, loadDiaryList } from '@/composables/useDiary'
import { me } from '@/composables/useAuth'
import { formatDate } from '@/lib/constants'

const heatmapColor = (type) => {
  if (type === 'cook') return 'bg-green-500'
  if (type === 'order') return 'bg-blue-500'
  if (type === 'both') return 'bg-purple-500'
  return 'bg-muted'
}

// 连续记录天数：基于 diaryList 中出现的日期集合，向前回溯今天/昨天…
const streakDays = computed(() => {
  if (!diaryList.value || diaryList.value.length === 0) return 0
  const dates = new Set(
    diaryList.value
      .map(d => (d.date || '').toString().slice(0, 10))
      .filter(Boolean)
  )
  if (dates.size === 0) return 0
  let streak = 0
  const cursor = new Date()
  cursor.setHours(0, 0, 0, 0)
  while (true) {
    const ds = cursor.toISOString().slice(0, 10)
    if (dates.has(ds)) {
      streak++
      cursor.setDate(cursor.getDate() - 1)
    } else {
      break
    }
  }
  return streak
})

const totalEntries = computed(() => (stats.value.cook_count || 0) + (stats.value.takeout_count || 0))

const heatmapPadding = computed(() => {
  if (!heatmapDays.value.length) return 0
  const first = heatmapDays.value[0]
  const d = new Date(first.date + 'T00:00:00')
  return (d.getDay() + 6) % 7 // 周一=0 … 周日=6
})

const WEEK_HEADERS = ['一', '二', '三', '四', '五', '六', '日']

const diaryTabs = [
  { value: '', label: '全部' },
  { value: 'cook', label: '做饭' },
  { value: 'order', label: '外卖' },
]

function typeBadgeClass(t) {
  if (t === 'cook') return 'bg-green-100 text-green-700 border-green-200'
  if (t === 'order') return 'bg-blue-100 text-blue-700 border-blue-200'
  return 'bg-muted text-muted-foreground'
}

function typeLabel(t) {
  return t === 'cook' ? '做饭' : t === 'order' ? '外卖' : '-'
}

onMounted(async () => {
  if (me.value) {
    await Promise.allSettled([loadStats(), loadHeatmap(), loadPrefWeights(), loadDiaryList()])
  }
})
</script>

<template>
  <div class="bg-background p-4 md:p-6 md:h-full md:flex md:flex-col md:min-h-0 md:overflow-hidden">
    <div class="w-full md:flex-1 md:flex md:flex-col md:min-h-0 md:gap-4">
      <!-- ========== 顶部标题栏 ========== -->
      <div class="md:shrink-0 flex items-baseline gap-3">
        <h1 class="text-xl md:text-2xl font-bold">📖 美食日记</h1>
        <span class="text-xs md:text-sm text-muted-foreground">记录每一餐，看见你的饮食偏好与节奏</span>
      </div>

      <!-- ========== 主体：桌面端左右双栏 ========== -->
      <div class="md:flex md:flex-1 md:min-h-0 md:gap-4">

        <!-- ===== 左栏：Stats + 偏好权重 + 日记列表（flex-1） ===== -->
        <div class="md:flex-1 md:min-h-0 md:min-w-0 md:flex md:flex-col md:gap-2">

          <!-- Stats 紧凑版 -->
          <div class="grid grid-cols-4 md:grid-cols-4 gap-1.5 md:shrink-0">
            <Card class="p-2">
              <div class="flex items-center gap-1.5">
                <span class="text-base">🍳</span>
                <div>
                  <div class="text-[10px] text-muted-foreground leading-none">做饭</div>
                  <div class="text-base font-bold leading-tight">{{ stats.cook_count || 0 }}</div>
                </div>
              </div>
            </Card>
            <Card class="p-2">
              <div class="flex items-center gap-1.5">
                <span class="text-base">🛵</span>
                <div>
                  <div class="text-[10px] text-muted-foreground leading-none">外卖</div>
                  <div class="text-base font-bold leading-tight">{{ stats.takeout_count || 0 }}</div>
                </div>
              </div>
            </Card>
            <Card class="p-2">
              <div class="flex items-center gap-1.5">
                <span class="text-base">🔥</span>
                <div>
                  <div class="text-[10px] text-muted-foreground leading-none">连续</div>
                  <div class="text-base font-bold leading-tight">{{ streakDays }}天</div>
                </div>
              </div>
            </Card>
            <Card class="p-2">
              <div class="flex items-center gap-1.5">
                <span class="text-base">📝</span>
                <div>
                  <div class="text-[10px] text-muted-foreground leading-none">累计</div>
                  <div class="text-base font-bold leading-tight">{{ totalEntries }}</div>
                </div>
              </div>
            </Card>
          </div>

          <!-- 偏好权重 Card -->
          <Card class="md:shrink-0">
            <CardHeader class="py-1.5 px-3">
              <CardTitle class="text-xs font-semibold leading-tight">偏好权重</CardTitle>
              <CardDescription class="text-[10px] leading-tight"></CardDescription>
            </CardHeader>
            <CardContent class="px-3 pb-2 pt-0 space-y-1.5">
              <div v-if="!prefWeights || prefWeights.length === 0" class="text-center text-[11px] text-muted-foreground py-2">
                暂无数据
              </div>
              <div v-for="p in prefWeights" :key="p.dimension" class="space-y-0.5">
                <div class="flex justify-between text-[11px]">
                  <span class="font-medium">{{ p.dimension }}</span>
                  <span class="text-muted-foreground">{{ Math.round(p.weight || 0) }}%</span>
                </div>
                <div class="h-1 rounded-full bg-muted overflow-hidden">
                  <div
                    class="h-full bg-primary rounded-full"
                    :style="{ width: Math.max(2, Math.round(p.weight || 0)) + '%' }"
                  ></div>
                </div>
              </div>
            </CardContent>
          </Card>

          <!-- 日记列表（主舞台，flex-1 占满剩余空间） -->
          <Card class="md:flex-1 md:min-h-0 md:min-w-0 md:flex md:flex-col">
            <CardHeader class="md:shrink-0 py-2 px-3">
              <div class="flex items-center justify-between gap-2">
                <div>
                  <CardTitle class="text-sm font-semibold leading-tight">日记列表</CardTitle>
                  <CardDescription class="text-[10px] leading-tight">共 {{ diaryList.length }} 条记录</CardDescription>
                </div>
                <Badge variant="outline" class="text-[10px]">
                  {{ diaryFilter === 'cook' ? '做饭' : diaryFilter === 'order' ? '外卖' : '全部' }}
                </Badge>
              </div>
            </CardHeader>
            <CardContent class="md:flex md:flex-col md:flex-1 md:min-h-0 md:overflow-hidden p-0">
              <Tabs v-model="diaryFilter" default-value="" class="md:flex md:flex-col md:flex-1 md:min-h-0">
                <!-- TabsList 仅作筛选器，内容区只渲染一次，切换 tab 不触发 DOM 重建，布局尺寸保持稳定 -->
                <TabsList class="md:shrink-0 mx-3 my-1">
                  <TabsTrigger
                    v-for="t in diaryTabs"
                    :key="t.value"
                    :value="t.value"
                    class="text-xs h-7"
                  >{{ t.label }}</TabsTrigger>
                </TabsList>

                <div class="md:mt-1 md:flex md:flex-col md:flex-1 md:min-h-0 md:overflow-hidden m-0 border-0 p-0">
                  <div class="min-h-[320px] md:flex-1 md:min-h-0 md:overflow-y-auto md:border-t md:border-x rounded-b-md bg-card [scrollbar-gutter:stable]">
                    <Table class="caption-bottom text-xs">
                      <TableHeader class="sticky top-0 z-10 bg-card border-b">
                        <TableRow>
                          <TableHead class="w-[100px] h-8">日期</TableHead>
                          <TableHead class="w-[60px] h-8">类型</TableHead>
                          <TableHead class="h-8">名称</TableHead>
                          <TableHead class="h-8">详情</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        <TableRow v-if="filteredDiary.length === 0">
                          <TableCell :colspan="4" class="text-center text-xs text-muted-foreground py-6">
                            暂无符合条件的日记
                          </TableCell>
                        </TableRow>
                        <TableRow v-for="d in filteredDiary" :key="d.id" class="h-9">
                          <TableCell class="text-xs whitespace-nowrap py-1">
                            {{ d.date ? formatDate(d.date) : '-' }}
                          </TableCell>
                          <TableCell class="py-1">
                            <Badge :class="typeBadgeClass(d.type)" class="text-[10px]">
                              {{ typeLabel(d.type) }}
                            </Badge>
                          </TableCell>
                          <TableCell class="text-xs font-medium py-1">{{ d.title || '-' }}</TableCell>
                          <TableCell class="text-xs text-muted-foreground py-1">
                            <span v-if="d.mood">心情：{{ d.mood }}</span>
                            <span v-if="d.cost !== undefined && d.cost !== null && d.cost !== 0"> · 花费：¥{{ d.cost }}</span>
                            <span v-if="d.rating"> · 评分：{{ d.rating }}</span>
                            <span v-if="!d.mood && (!d.cost) && !d.rating">-</span>
                          </TableCell>
                        </TableRow>
                      </TableBody>
                    </Table>
                  </div>
                </div>
              </Tabs>
            </CardContent>
          </Card>
        </div>

        <!-- ===== 右栏：只有热力图（flex-2，占 2/3 宽度） ===== -->
        <Card class="md:flex-[2] md:shrink-0 md:flex md:flex-col md:h-full">
          <CardHeader class="md:shrink-0 py-3 px-4">
            <div class="flex items-center justify-between">
              <CardTitle class="text-base font-semibold">饮食热力图</CardTitle>
            </div>
            <CardDescription class="text-[11px]">{{ currentYearMonth }} · 本月 {{ heatmapDays.filter(d => d.type).length }} 天有记录</CardDescription>
            <div class="flex items-center gap-2 text-[10px] text-muted-foreground pt-1">
              <span class="flex items-center gap-0.5"><span class="w-2.5 h-2.5 rounded-sm bg-green-500" />做饭</span>
              <span class="flex items-center gap-0.5"><span class="w-2.5 h-2.5 rounded-sm bg-blue-500" />外卖</span>
              <span class="flex items-center gap-0.5"><span class="w-2.5 h-2.5 rounded-sm bg-purple-500" />都有</span>
            </div>
          </CardHeader>
          <CardContent class="md:flex md:flex-col md:flex-1 md:min-h-0 overflow-y-auto px-4 pb-4 pt-0">
            <div class="grid grid-cols-7 gap-1 text-center text-[10px] text-muted-foreground mb-1">
              <div v-for="w in WEEK_HEADERS" :key="w" class="h-4 leading-4">{{ w }}</div>
            </div>
            <div class="grid grid-cols-7 gap-1">
              <div
                v-for="n in heatmapPadding"
                :key="'pad-' + n"
                class="aspect-square rounded-sm bg-muted/20"
              ></div>
              <div
                  v-for="d in heatmapDays"
                  :key="d.date"
                  :title="d.date + (d.title ? ' · ' + d.title : '')"
                  :class="[
                    'aspect-square rounded-sm flex items-center justify-center text-xs font-medium',
                    heatmapColor(d.type),
                    d.isToday ? 'ring-2 ring-primary ring-offset-1' : '',
                    d.type ? 'text-white' : 'text-muted-foreground'
                  ]"
                >{{ d.day }}</div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  </div>
</template>
