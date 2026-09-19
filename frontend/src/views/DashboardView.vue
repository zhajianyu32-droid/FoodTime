<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { me, quota, env, reloadMe } from '@/composables/useAuth'
import { recipeQuotaPercent, fortuneQuotaPercent, chatQuotaPercent } from '@/composables/useQuota'
import { expiredCount, expiringCount, loadIngredients } from '@/composables/useCook'
import { shoppingPendingCount, shoppingCheckedCount, loadShopping } from '@/composables/useShopping'
import { loadStats, loadHeatmap, loadDiaryList, loadPrefWeights } from '@/composables/useDiary'

const router = useRouter()

onMounted(async () => {
  await reloadMe()
  await Promise.allSettled([
    loadIngredients(), loadShopping(),
    loadStats(), loadHeatmap(), loadDiaryList(), loadPrefWeights(),
  ])
})
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div>
      <h1 class="text-2xl font-bold">🏠 仪表盘</h1>
      <p class="text-sm text-muted-foreground">欢迎回来，{{ me?.username }}</p>
    </div>

    <!-- LLM Quota Cards -->
    <div class="grid gap-4 md:grid-cols-3">
      <Card>
        <CardHeader class="pb-2">
          <CardDescription>菜谱推荐</CardDescription>
          <CardTitle class="text-2xl">{{ quota.LLM_RECIPES_QUOTA }} / {{ quota.LLM_RECIPES_TOTAL }}</CardTitle>
        </CardHeader>
        <CardContent>
          <Progress :model-value="recipeQuotaPercent" />
          <p class="mt-1 text-xs text-muted-foreground">已使用 {{ recipeQuotaPercent }}%</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader class="pb-2">
          <CardDescription>美食运势</CardDescription>
          <CardTitle class="text-2xl">{{ quota.LLM_FORTUNE_QUOTA }} / {{ quota.LLM_FORTUNE_TOTAL }}</CardTitle>
        </CardHeader>
        <CardContent>
          <Progress :model-value="fortuneQuotaPercent" />
          <p class="mt-1 text-xs text-muted-foreground">已使用 {{ fortuneQuotaPercent }}%</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader class="pb-2">
          <CardDescription>对话次数</CardDescription>
          <CardTitle class="text-2xl">{{ quota.LLM_CHAT_QUOTA }} / {{ quota.LLM_CHAT_TOTAL }}</CardTitle>
        </CardHeader>
        <CardContent>
          <Progress :model-value="chatQuotaPercent" />
          <p class="mt-1 text-xs text-muted-foreground">已使用 {{ chatQuotaPercent }}%</p>
        </CardContent>
      </Card>
    </div>

    <!-- Quick Stats -->
    <div class="grid gap-4 md:grid-cols-2">
      <Card class="cursor-pointer hover:shadow-md transition-shadow" @click="router.push('/ingredients')">
        <CardHeader>
          <CardTitle class="text-lg">🧊 食材库</CardTitle>
        </CardHeader>
        <CardContent class="flex items-center gap-6">
          <div class="flex flex-col items-center">
            <span class="text-2xl font-bold text-destructive">{{ expiredCount }}</span>
            <span class="text-xs text-muted-foreground">已过期</span>
          </div>
          <div class="flex flex-col items-center">
            <span class="text-2xl font-bold text-yellow-600">{{ expiringCount }}</span>
            <span class="text-xs text-muted-foreground">即将过期</span>
          </div>
        </CardContent>
      </Card>

      <Card class="cursor-pointer hover:shadow-md transition-shadow" @click="router.push('/shopping')">
        <CardHeader>
          <CardTitle class="text-lg">🛒 购物单</CardTitle>
        </CardHeader>
        <CardContent class="flex items-center gap-6">
          <div class="flex flex-col items-center">
            <span class="text-2xl font-bold">{{ shoppingPendingCount }}</span>
            <span class="text-xs text-muted-foreground">待购买</span>
          </div>
          <div class="flex flex-col items-center">
            <span class="text-2xl font-bold text-green-600">{{ shoppingCheckedCount }}</span>
            <span class="text-xs text-muted-foreground">已购买</span>
          </div>
        </CardContent>
      </Card>
    </div>

    <!-- Quick Navigation -->
    <div class="grid gap-4 md:grid-cols-2">
      <Card class="cursor-pointer hover:shadow-md transition-shadow" @click="router.push('/cook')">
        <CardHeader>
          <CardTitle class="text-lg">🍳 Cook Mode</CardTitle>
          <CardDescription>从冰箱食材出发，获取 AI 菜谱推荐</CardDescription>
        </CardHeader>
      </Card>

      <Card class="cursor-pointer hover:shadow-md transition-shadow" @click="router.push('/order')">
        <CardHeader>
          <CardTitle class="text-lg">🛵 Order Mode</CardTitle>
          <CardDescription>抽取美食运势，与 AI 对话获取外卖推荐</CardDescription>
        </CardHeader>
      </Card>
    </div>
  </div>
</template>
