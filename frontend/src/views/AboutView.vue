<script setup>
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { env } from '@/composables/useAuth'
</script>

<template>
  <div class="min-h-screen bg-background p-4 md:p-8">
    <div class="max-w-3xl mx-auto space-y-6">
      <!-- Page header -->
      <div>
        <h1 class="text-2xl font-bold">📖 关于</h1>
        <p class="text-sm text-muted-foreground">了解 FoodTime 背后的故事与技术栈</p>
      </div>

      <!-- Project info card -->
      <Card>
        <CardHeader>
          <div class="flex items-center justify-between gap-2">
            <div>
              <CardTitle class="text-2xl">食光 FoodTime</CardTitle>
              <CardDescription>独居青年吃饭决策助手</CardDescription>
            </div>
            <Badge variant="secondary">{{ env }}</Badge>
          </div>
        </CardHeader>
        <CardContent class="space-y-4">
          <p class="text-sm text-muted-foreground leading-relaxed">
            FoodTime 是一个面向独居青年的智能吃饭决策助手，结合 LLM 能力与个人偏好档案，
            帮你解决「今天吃什么」「冰箱里这些食材能做什么」「该做饭还是点外卖」等日常难题。
            支持食材库存管理、AI 菜谱推荐、外卖决策对话、美食日记记录与偏好画像沉淀。
          </p>

          <!-- Tech stack badges -->
          <div>
            <p class="text-xs font-medium text-muted-foreground mb-2">技术栈</p>
            <div class="flex flex-wrap gap-1.5">
              <Badge variant="outline">FastAPI</Badge>
              <Badge variant="outline">Vue 3</Badge>
              <Badge variant="outline">SQLAlchemy</Badge>
              <Badge variant="outline">Tailwind CSS</Badge>
              <Badge variant="outline">shadcn-vue</Badge>
              <Badge variant="outline">LLM</Badge>
            </div>
          </div>

          <!-- Meta info table -->
          <div class="grid grid-cols-2 gap-y-3 gap-x-4 text-sm pt-3 border-t">
            <div>
              <p class="text-xs text-muted-foreground">项目名称</p>
              <p class="font-medium">FoodTime · 食光</p>
            </div>
            <div>
              <p class="text-xs text-muted-foreground">版本</p>
              <p class="font-medium">v0.1.0</p>
            </div>
            <div>
              <p class="text-xs text-muted-foreground">后端</p>
              <p class="font-medium">FastAPI + SQLAlchemy</p>
            </div>
            <div>
              <p class="text-xs text-muted-foreground">前端</p>
              <p class="font-medium">Vue 3 + shadcn-vue</p>
            </div>
            <div>
              <p class="text-xs text-muted-foreground">运行环境</p>
              <p class="font-medium">{{ env }}</p>
            </div>
            <div>
              <p class="text-xs text-muted-foreground">许可</p>
              <p class="font-medium">MIT</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <!-- Feature highlights card -->
      <Card>
        <CardHeader>
          <CardTitle class="text-lg">核心能力</CardTitle>
          <CardDescription>FoodTime 提供的几大场景化能力</CardDescription>
        </CardHeader>
        <CardContent>
          <ul class="space-y-2 text-sm text-muted-foreground">
            <li>🍳 <span class="font-medium text-foreground">Cook Mode</span>：选冰箱食材 → AI 推荐菜谱，一键记录做饭或加入购物单补货</li>
            <li>🛒 <span class="font-medium text-foreground">购物清单</span>：按推荐菜谱缺料自动生成，勾选已购即同步入库</li>
            <li>🥡 <span class="font-medium text-foreground">外卖决策</span>：和 AI 对话几轮，让 LLM 推荐今天点什么外卖</li>
            <li>🥬 <span class="font-medium text-foreground">食材管理</span>：冰箱食材统一登记，自动临期/过期提醒</li>
            <li>📖 <span class="font-medium text-foreground">美食日记</span>：做饭/外卖记录沉淀，生成偏好权重与饮食热力图</li>
            <li>⚙️ <span class="font-medium text-foreground">偏好档案</span>：星座/属相/MBTI/口味/菜系/厨具/忌口三层树</li>
          </ul>
        </CardContent>
      </Card>
    </div>
  </div>
</template>
