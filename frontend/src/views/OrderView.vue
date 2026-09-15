<script setup>
import { ref, computed, nextTick } from 'vue'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  fortune, drawFortune, chatSession, chatRound, chatMsgs, lastQuestion, finalRecommend, loading, chatBox,
  startChat, sendAnswer, resetChat, saveTakeout, scrollChat,
} from '@/composables/useOrder'
import { me, quota } from '@/composables/useAuth'
import { showToast } from '@/composables/useToast'

const flipped = ref(false)

function flipCard() {
  if (!fortune.value) return
  flipped.value = !flipped.value
}

async function doDrawFortune() {
  if (loading.fortune || fortune.value) return
  await drawFortune()
  if (!fortune.value) return
  // 预渲染分帧：等 3D 卡牌完成挂载与首帧绘制（GPU 层提升）后再触发翻转，
  // 避免挂载、光栅化、动画三者叠加导致第一次翻转掉帧
  await nextTick()
  await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))
  flipped.value = true
}

// ===== 流程步骤：① 抽运势 → ② 5轮对话 → ③ 拿推荐 =====
const currentStep = computed(() => {
  if (!fortune.value) return 1
  if (!finalRecommend.value) return 2
  return 3
})
const STEPS = [
  { n: 1, label: '抽运势' },
  { n: 2, label: '5 轮对话' },
  { n: 3, label: '拿推荐' },
]
function stepClass(n) {
  return { done: n < currentStep.value, active: n === currentStep.value }
}
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h1 class="text-2xl font-bold tracking-tight">🛵 Order Mode</h1>
        <p class="text-sm text-muted-foreground mt-0.5">抽今日美食运势卡，和 AI 聊 5 轮，拿专属外卖推荐</p>
      </div>
      <div class="flex items-center gap-2">
        <Badge variant="secondary">运势 {{ quota.LLM_FORTUNE_QUOTA }}/{{ quota.LLM_FORTUNE_TOTAL }}</Badge>
        <Badge variant="secondary">对话 {{ quota.LLM_CHAT_QUOTA }}/{{ quota.LLM_CHAT_TOTAL }}</Badge>
      </div>
    </div>

    <!-- 流程步骤指示条 -->
    <div class="step-bar">
      <template v-for="(s, i) in STEPS" :key="s.n">
        <div class="step-item" :class="stepClass(s.n)">
          <span class="step-dot">{{ s.n < currentStep ? '✓' : s.n }}</span>
          <span class="step-label">{{ s.label }}</span>
        </div>
        <div v-if="i < STEPS.length - 1" class="step-line" :class="{ done: s.n < currentStep }"></div>
      </template>
    </div>

    <!-- 左右两列布局 -->
    <div class="grid gap-6 lg:grid-cols-2 min-h-[520px]">

      <!-- ============ 左：美食运势卡牌 ============ -->
      <div class="flex flex-col">
        <div class="flex items-center justify-between mb-3">
          <h2 class="text-sm font-semibold text-muted-foreground uppercase tracking-wide">今日美食运势</h2>
          <Badge v-if="fortune" variant="outline" class="text-xs">点击卡牌翻转</Badge>
        </div>

        <!-- 3D 翻转卡牌容器 -->
        <div class="flex-1 flex items-center justify-center" style="perspective: 1200px;">
          <!-- 未抽取状态 -->
          <div v-if="!fortune" class="text-center space-y-4 py-6">
            <div
              class="fortune-card-back-static"
              :class="loading.fortune ? 'drawing' : 'idle'"
              @click="doDrawFortune"
            >
              <svg class="card-back-svg" viewBox="0 0 340 480" xmlns="http://www.w3.org/2000/svg">
                <use href="#cardBackArt" />
              </svg>
              <div class="card-back-label">{{ loading.fortune ? '正在解签…' : '点击翻牌' }}</div>
            </div>
            <p class="text-sm text-muted-foreground">每天一签，指引你今天宜吃什么</p>
          </div>

          <!-- 翻转卡牌 -->
          <div
            v-else
            class="fortune-card-3d"
            :class="{ 'flipped': flipped }"
            @click="flipCard"
          >
            <!-- 卡背 -->
            <div class="fortune-card face-back">
              <svg class="card-back-svg" viewBox="0 0 340 480" xmlns="http://www.w3.org/2000/svg">
                <use href="#cardBackArt" />
              </svg>
              <div v-if="fortune.cached" class="card-back-badge">今日已抽</div>
            </div>

            <!-- 卡面 -->
            <div class="fortune-card face-front">
              <!-- 装饰边框 · 银刻双线框 + 四角内凹四芒（框线在距角 33px 处收住，插进芒尖） -->
              <div class="card-border-deco">
                <svg class="card-deco-svg" viewBox="0 0 340 480" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                  <rect x="0.5" y="0.5" width="339" height="479" rx="16" fill="none" stroke="#C8C6C2" stroke-width="1" opacity="0.6"/>
                  <g fill="none" stroke="#8A8884" stroke-width="0.7" opacity="0.7">
                    <path d="M 33 10 L 307 10"/>
                    <path d="M 33 470 L 307 470"/>
                    <path d="M 10 33 L 10 447"/>
                    <path d="M 330 33 L 330 447"/>
                  </g>
                  <g fill="none" stroke="#FFFFFF" stroke-width="0.9" opacity="0.5">
                    <path d="M 33 11.2 L 307 11.2"/>
                    <path d="M 33 471.2 L 307 471.2"/>
                    <path d="M 11.2 33 L 11.2 447"/>
                    <path d="M 331.2 33 L 331.2 447"/>
                  </g>
                  <g fill="none" stroke="#8A8884" stroke-width="0.35" opacity="0.42">
                    <path d="M 33 16.5 L 307 16.5"/>
                    <path d="M 33 463.5 L 307 463.5"/>
                    <path d="M 16.5 33 L 16.5 447"/>
                    <path d="M 323.5 33 L 323.5 447"/>
                  </g>
                  <g fill="none" stroke="#8A8884" stroke-width="0.7" opacity="0.9">
                    <path d="M 20 7.5 Q 23.4 16.6 32.5 20 Q 23.4 23.4 20 32.5 Q 16.6 23.4 7.5 20 Q 16.6 16.6 20 7.5 Z"/>
                    <path d="M 320 7.5 Q 323.4 16.6 332.5 20 Q 323.4 23.4 320 32.5 Q 316.6 23.4 307.5 20 Q 316.6 16.6 320 7.5 Z"/>
                    <path d="M 20 447.5 Q 23.4 456.6 32.5 460 Q 23.4 463.4 20 472.5 Q 16.6 463.4 7.5 460 Q 16.6 456.6 20 447.5 Z"/>
                    <path d="M 320 447.5 Q 323.4 456.6 332.5 460 Q 323.4 463.4 320 472.5 Q 316.6 463.4 307.5 460 Q 316.6 456.6 320 447.5 Z"/>
                  </g>
                  <g fill="none" stroke="#8A8884" stroke-width="0.45" opacity="0.75">
                    <path d="M 20 15.5 L 24.5 20 L 20 24.5 L 15.5 20 Z"/>
                    <path d="M 320 15.5 L 324.5 20 L 320 24.5 L 315.5 20 Z"/>
                    <path d="M 20 455.5 L 24.5 460 L 20 464.5 L 15.5 460 Z"/>
                    <path d="M 320 455.5 L 324.5 460 L 320 464.5 L 315.5 460 Z"/>
                  </g>
                </svg>
              </div>

              <!-- 卡面内容 -->
              <div class="card-front-content">
                <!-- 身份标签 -->
                <div class="card-id-row">
                  <span class="card-id-badge">{{ fortune.zodiac }}</span>
                  <span class="card-id-badge alt">属{{ fortune.chinese_zodiac }}</span>
                  <span class="card-id-badge alt">{{ fortune.mbti }}</span>
                </div>

                <!-- 今日历法（农历·节气·黄历宜忌） -->
                <div v-if="fortune.lunar_date" class="card-almanac">
                  <div class="almanac-date-row">
                    <span class="almanac-date">{{ fortune.lunar_date }}</span>
                    <span v-if="fortune.solar_term" class="almanac-term">{{ fortune.solar_term }}</span>
                  </div>
                  <div v-if="(fortune.yi || []).length" class="almanac-yiji">
                    <span class="yiji-label">宜</span>
                    <span class="yiji-text">{{ fortune.yi.slice(0, 4).join(' · ') }}</span>
                  </div>
                  <div v-if="(fortune.ji || []).length" class="almanac-yiji">
                    <span class="yiji-label ji">忌</span>
                    <span class="yiji-text">{{ fortune.ji.slice(0, 4).join(' · ') }}</span>
                  </div>
                </div>

                <!-- 幸运三元素 -->
                <div class="card-lucky-row">
                  <div class="lucky-item">
                    <span class="lucky-label">幸运食物</span>
                    <span class="lucky-value food">{{ fortune.lucky_food || '-' }}</span>
                  </div>
                  <div class="lucky-divider"></div>
                  <div class="lucky-item">
                    <span class="lucky-label">幸运颜色</span>
                    <span class="lucky-value color">{{ fortune.lucky_color || '-' }}</span>
                  </div>
                  <div class="lucky-divider"></div>
                  <div class="lucky-item">
                    <span class="lucky-label">幸运数字</span>
                    <span class="lucky-value number">{{ fortune.lucky_number ?? '-' }}</span>
                  </div>
                </div>

                <!-- 食物关键词 -->
                <div v-if="(fortune.food_keywords || []).length" class="card-keywords">
                  <span
                    v-for="k in fortune.food_keywords"
                    :key="k"
                    class="keyword-tag"
                  >{{ k }}</span>
                </div>

                <!-- 综合建议 -->
                <div class="card-suggestion">
                  <div class="suggestion-head">
                    <span class="suggestion-rule"></span>
                    <span class="suggestion-label">综合建议</span>
                    <span class="suggestion-rule"></span>
                  </div>
                  <p class="suggestion-text">{{ fortune.suggestion || '暂无建议' }}</p>
                </div>

                <!-- 翻回提示 -->
                <p class="card-flip-hint">点击翻回 ↺</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ============ 右：AI 对话推荐 ============ -->
      <div class="flex flex-col">
        <div class="flex items-center justify-between mb-3">
          <h2 class="text-sm font-semibold text-muted-foreground uppercase tracking-wide">AI 对话推荐</h2>
          <Badge v-if="chatSession" variant="default" class="text-xs">第 {{ chatRound }}/5 轮</Badge>
        </div>

        <!-- 对话卡片 -->
        <div
          class="chat-container flex-1 flex flex-col"
          :class="{ 'chat-nudge': currentStep === 2 && !chatSession && !loading.chatStart }"
        >
          <!-- 未开始 -->
          <div v-if="!chatSession && !finalRecommend" class="flex-1 flex items-center justify-center">
            <div class="text-center space-y-4 py-12">
              <div class="text-5xl opacity-20 mb-2">💬</div>
              <p class="text-sm text-muted-foreground">开始一段对话，让 AI 了解你今天的口味</p>
              <p class="text-xs text-muted-foreground">5 轮快问快答，AI 综合运势与偏好给出外卖推荐</p>
              <Button :disabled="loading.chatStart" @click="startChat">
                {{ loading.chatStart ? '创建会话中…' : '🤖 开始对话' }}
              </Button>
            </div>
          </div>

          <!-- 对话进行中 -->
          <template v-else>
            <!-- 消息流 -->
            <div
              ref="chatBox"
              class="chat-messages flex-1 overflow-y-auto"
            >
              <div
                v-for="msg in chatMsgs"
                :key="msg.id"
                class="msg-row"
                :class="msg.role === 'user' ? 'msg-user' : 'msg-ai'"
              >
                <div class="msg-avatar" :class="msg.role === 'user' ? 'avatar-user' : 'avatar-ai'">
                  {{ msg.role === 'user' ? '🧑' : '🤖' }}
                </div>
                <div class="msg-bubble" :class="msg.role === 'user' ? 'bubble-user' : 'bubble-ai'">
                  {{ msg.text }}
                </div>
              </div>

              <!-- AI 思考中 -->
              <div v-if="loading.chatTurn" class="msg-row msg-ai">
                <div class="msg-avatar avatar-ai">🤖</div>
                <div class="msg-bubble bubble-ai thinking">
                  <span class="dot-flashing"></span>
                  <span class="dot-flashing"></span>
                  <span class="dot-flashing"></span>
                </div>
              </div>
            </div>

            <!-- 当前问题 + 选项 -->
            <div v-if="lastQuestion && !loading.chatTurn" class="question-area">
              <p class="question-text">{{ lastQuestion.question }}</p>
              <div class="option-chips">
                <button
                  v-for="opt in (lastQuestion.options || [])"
                  :key="opt"
                  class="option-chip"
                  @click="sendAnswer(opt)"
                >{{ opt }}</button>
              </div>
            </div>

            <!-- 最终推荐 -->
            <div v-if="finalRecommend" class="final-recommend">
              <div class="final-header">
                <span class="final-icon">🎯</span>
                <span class="final-title">{{ finalRecommend.final_recommend || '-' }}</span>
              </div>
              <p v-if="finalRecommend.recommend_reason" class="final-reason">
                {{ finalRecommend.recommend_reason }}
              </p>
              <div v-if="(finalRecommend.alternatives || []).length" class="final-alts">
                <span class="alts-label">备选</span>
                <span v-for="a in finalRecommend.alternatives" :key="a" class="alt-tag">{{ a }}</span>
              </div>
              <div class="final-actions">
                <!-- 多平台外卖入口：App Scheme + 搜索引擎兜底 -->
                <div class="delivery-links">
                  <a v-if="finalRecommend.delivery_urls?.meituan" :href="finalRecommend.delivery_urls.meituan" class="delivery-link" title="唤起美团 App">
                    <span class="delivery-icon">🛵</span>
                    <span class="delivery-label">美团</span>
                  </a>
                  <a v-if="finalRecommend.delivery_urls?.bing" :href="finalRecommend.delivery_urls.bing" target="_blank" rel="noopener noreferrer" class="delivery-link" title="必应搜索">
                    <span class="delivery-icon">🔎</span>
                    <span class="delivery-label">必应</span>
                  </a>
                  <a v-if="finalRecommend.delivery_urls?.baidu" :href="finalRecommend.delivery_urls.baidu" target="_blank" rel="noopener noreferrer" class="delivery-link" title="百度搜索">
                    <span class="delivery-icon">🔎</span>
                    <span class="delivery-label">百度</span>
                  </a>
                  <a v-else-if="finalRecommend.meituan_url" :href="finalRecommend.meituan_url" target="_blank" rel="noopener noreferrer" class="delivery-link">
                    <span class="delivery-icon">🔎</span>
                    <span class="delivery-label">搜索外卖</span>
                  </a>
                </div>
                <div class="feedback-group">
                  <Button size="sm" variant="ghost" class="text-green-600" @click="saveTakeout(finalRecommend, '好吃')">👍 好吃</Button>
                  <Button size="sm" variant="ghost" @click="saveTakeout(finalRecommend, '一般')">😐 一般</Button>
                  <Button size="sm" variant="ghost" class="text-red-600" @click="saveTakeout(finalRecommend, '不好吃')">👎 不好吃</Button>
                </div>
                <Button size="sm" variant="ghost" @click="resetChat">重置</Button>
              </div>
            </div>
          </template>
        </div>
      </div>
    </div>
  </div>

  <!-- 卡背 SVG 共享定义 · 银刻（方向 D） -->
  <!-- viewBox: 340x480, 中心(170,240) -->
  <!-- 线宽全部 0.35~1px；双线框各段在距角 33px 处收住、插进角徽臂尖 -->
  <!-- 蚀刻浮雕：每条刻线下方压 1px 白线；全卡唯一焦点是中心星盘（八芒长尖 r72 触到点线环 r73） -->
  <svg width="0" height="0" style="position:absolute;">
    <defs>
      <!-- 银刻渐变：卡底 / 芒面 / 月牙面 -->
      <linearGradient id="cbBg" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#F7F6F3"/>
        <stop offset="0.42" stop-color="#EEEDEA"/>
        <stop offset="1" stop-color="#DFDEDA"/>
      </linearGradient>
      <linearGradient id="cbStar" x1="0.15" y1="0" x2="0.85" y2="1">
        <stop offset="0" stop-color="#DCDBD7"/>
        <stop offset="1" stop-color="#F4F3F0"/>
      </linearGradient>
      <linearGradient id="cbCrescent" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0" stop-color="#9C9A96"/>
        <stop offset="1" stop-color="#ECEBE8"/>
      </linearGradient>

      <g id="cardBackArt">
        <!-- 冷银底 -->
        <rect x="0" y="0" width="340" height="480" rx="16" fill="url(#cbBg)"/>
        <rect x="0.5" y="0.5" width="339" height="479" rx="16" fill="none" stroke="#C8C6C2" stroke-width="1" opacity="0.6"/>

        <!-- ============ 双线框（各段在距角 33px 处收住） ============ -->
        <g fill="none" stroke="#8A8884" stroke-width="0.7" opacity="0.7">
          <path d="M 33 10 L 307 10"/>
          <path d="M 33 470 L 307 470"/>
          <path d="M 10 33 L 10 447"/>
          <path d="M 330 33 L 330 447"/>
        </g>
        <!-- 蚀刻浮雕：刻线下方压 1px 白线 -->
        <g fill="none" stroke="#FFFFFF" stroke-width="0.9" opacity="0.5">
          <path d="M 33 11.2 L 307 11.2"/>
          <path d="M 33 471.2 L 307 471.2"/>
          <path d="M 11.2 33 L 11.2 447"/>
          <path d="M 331.2 33 L 331.2 447"/>
        </g>
        <!-- 内细框 -->
        <g fill="none" stroke="#8A8884" stroke-width="0.35" opacity="0.42">
          <path d="M 33 16.5 L 307 16.5"/>
          <path d="M 33 463.5 L 307 463.5"/>
          <path d="M 16.5 33 L 16.5 447"/>
          <path d="M 323.5 33 L 323.5 447"/>
        </g>

        <!-- ============ 四角内凹四芒徽（压在框角上） ============ -->
        <g fill="none" stroke="#8A8884" stroke-width="0.7" opacity="0.9">
          <path d="M 20 7.5 Q 23.4 16.6 32.5 20 Q 23.4 23.4 20 32.5 Q 16.6 23.4 7.5 20 Q 16.6 16.6 20 7.5 Z"/>
          <path d="M 320 7.5 Q 323.4 16.6 332.5 20 Q 323.4 23.4 320 32.5 Q 316.6 23.4 307.5 20 Q 316.6 16.6 320 7.5 Z"/>
          <path d="M 20 447.5 Q 23.4 456.6 32.5 460 Q 23.4 463.4 20 472.5 Q 16.6 463.4 7.5 460 Q 16.6 456.6 20 447.5 Z"/>
          <path d="M 320 447.5 Q 323.4 456.6 332.5 460 Q 323.4 463.4 320 472.5 Q 316.6 463.4 307.5 460 Q 316.6 456.6 320 447.5 Z"/>
        </g>
        <g fill="none" stroke="#8A8884" stroke-width="0.45" opacity="0.75">
          <path d="M 20 15.5 L 24.5 20 L 20 24.5 L 15.5 20 Z"/>
          <path d="M 320 15.5 L 324.5 20 L 320 24.5 L 315.5 20 Z"/>
          <path d="M 20 455.5 L 24.5 460 L 20 464.5 L 15.5 460 Z"/>
          <path d="M 320 455.5 L 324.5 460 L 320 464.5 L 315.5 460 Z"/>
        </g>

        <!-- ============ 左右点线竖列 + 中置银珠（y=240 与星盘心同高） ============ -->
        <g fill="none" stroke="#8A8884" stroke-width="1.7" stroke-linecap="round" stroke-dasharray="1.5 6" opacity="0.75">
          <path d="M 44 98 L 44 212"/>
          <path d="M 44 268 L 44 382"/>
          <path d="M 296 98 L 296 212"/>
          <path d="M 296 268 L 296 382"/>
        </g>
        <circle cx="44" cy="240" r="4.2" fill="#8A8884" opacity="0.8"/>
        <circle cx="44" cy="240" r="1.9" fill="#EFEEEC"/>
        <circle cx="296" cy="240" r="4.2" fill="#8A8884" opacity="0.8"/>
        <circle cx="296" cy="240" r="1.9" fill="#EFEEEC"/>

        <!-- ============ 上下对称箭羽 ============ -->
        <g fill="none" stroke="#8A8884" stroke-width="0.55" stroke-linecap="round" opacity="0.85">
          <path d="M 170 35 L 170 138"/>
          <path d="M 170 36 L 164 84"/>
          <path d="M 170 36 L 176 84"/>
          <path d="M 158 104 L 170 112 L 182 104"/>
          <path d="M 160 116 L 170 123 L 180 116"/>
          <path d="M 162 126 L 170 132 L 178 126"/>
          <path d="M 170 445 L 170 342"/>
          <path d="M 170 444 L 164 396"/>
          <path d="M 170 444 L 176 396"/>
          <path d="M 158 376 L 170 368 L 182 376"/>
          <path d="M 160 364 L 170 357 L 180 364"/>
          <path d="M 162 354 L 170 348 L 178 354"/>
        </g>
        <path d="M 170 89 L 175 94 L 170 99 L 165 94 Z" fill="#8A8884" opacity="0.5"/>
        <path d="M 170 391 L 175 386 L 170 381 L 165 386 Z" fill="#8A8884" opacity="0.5"/>

        <!-- ============ 中心星盘 ============ -->
        <circle cx="170" cy="241.2" r="92" fill="none" stroke="#FFFFFF" stroke-width="1.3" opacity="0.75"/>
        <circle cx="170" cy="240" r="92" fill="none" stroke="#8A8884" stroke-width="0.95" opacity="0.85"/>
        <circle cx="170" cy="240" r="87" fill="none" stroke="#8A8884" stroke-width="0.4" opacity="0.55"/>
        <circle cx="170" cy="240" r="73" fill="none" stroke="#8A8884" stroke-width="1.5" stroke-linecap="round" stroke-dasharray="1 10.4" opacity="0.7"/>
        <!-- 八芒：四长尖 r72（恰好触到点线环）、四短尖 r51 -->
        <g fill="url(#cbStar)" stroke="#8A8884" stroke-width="0.5" opacity="0.92">
          <path d="M 170 168 L 179 218 L 161 218 Z"/>
          <path d="M 242 240 L 192 231 L 192 249 Z"/>
          <path d="M 170 312 L 161 262 L 179 262 Z"/>
          <path d="M 98 240 L 148 249 L 148 231 Z"/>
          <path d="M 206 204 L 190 229 L 181 220 Z"/>
          <path d="M 134 204 L 150 229 L 159 220 Z"/>
          <path d="M 206 276 L 190 251 L 181 260 Z"/>
          <path d="M 134 276 L 150 251 L 159 260 Z"/>
        </g>
        <!-- 中心盘 + 月牙 -->
        <circle cx="170" cy="241.2" r="21" fill="none" stroke="#FFFFFF" stroke-width="1.2" opacity="0.85"/>
        <circle cx="170" cy="240" r="21" fill="#F6F5F2" stroke="#8A8884" stroke-width="0.6"/>
        <path d="M 169.96 225.04 A 16 16 0 1 0 180.7 251.9 A 15 15 0 0 1 169.96 225.04 Z" fill="url(#cbCrescent)" stroke="#8A8884" stroke-width="0.5"/>
      </g>
    </defs>
  </svg>
</template>

<style scoped>
/* ========== 运势卡牌 3D 翻转 ========== */

/* 卡牌容器 */
.fortune-card-3d {
  width: min(340px, 100%);
  height: auto;
  aspect-ratio: 340 / 480;
  position: relative;
  cursor: pointer;
  transform-style: preserve-3d;
  transition: transform 0.7s cubic-bezier(0.4, 0.2, 0.2, 1);
  will-change: transform; /* 预提升 GPU 合成层，首次翻转不再掉帧 */
}
.fortune-card-3d.flipped {
  transform: rotateY(180deg);
}

/* 卡牌面共通 */
.fortune-card {
  position: absolute;
  inset: 0;
  backface-visibility: hidden;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 10px 28px rgba(0,0,0,0.13), 0 2px 6px rgba(0,0,0,0.06);
}

/* 卡背 */
.face-back {
  background: #EFEEEC;
}
.card-back-svg {
  width: 100%;
  height: 100%;
  display: block;
}
.card-back-badge {
  position: absolute;
  top: 12px;
  right: 12px;
  background: rgba(255,255,255,0.55);
  color: #6E6B67;
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 8px;
  border: 1px solid rgba(138,136,132,0.45);
  letter-spacing: 0.05em;
}
.card-back-label {
  position: absolute;
  bottom: 26px;
  left: 50%;
  transform: translateX(-50%);
  font-size: 11px;
  color: #8E8A85;
  letter-spacing: 0.15em;
  text-transform: uppercase;
  pointer-events: none;
}

/* 静态卡背（未抽取时）· 尺寸与翻转卡对齐，消除抽牌瞬间的跳变与底色缝 */
.fortune-card-back-static {
  width: min(340px, 100%);
  height: auto;
  aspect-ratio: 340 / 480;
  border-radius: 16px;
  cursor: pointer;
  transition: transform 0.3s;
  background: #EFEEEC;
  box-shadow: 0 10px 28px rgba(0,0,0,0.13), 0 2px 6px rgba(0,0,0,0.06);
  overflow: hidden;
  position: relative;
  margin: 0 auto;
}
.fortune-card-back-static:hover {
  transform: translateY(-4px) scale(1.02);
  box-shadow: 0 16px 40px rgba(0,0,0,0.18), 0 6px 12px rgba(0,0,0,0.12);
}
.fortune-card-back-static .card-back-svg {
  width: 100%;
  height: 100%;
}

/* 待机呼吸：吸引首次点击 */
.fortune-card-back-static.idle {
  animation: cardIdle 3.2s ease-in-out infinite;
}
@keyframes cardIdle {
  0%, 100% { transform: translateY(0) scale(1); box-shadow: 0 10px 28px rgba(0,0,0,0.13), 0 2px 6px rgba(0,0,0,0.06); }
  50% { transform: translateY(-6px) scale(1.015); box-shadow: 0 18px 44px rgba(0,0,0,0.18), 0 4px 10px rgba(0,0,0,0.1); }
}

/* 抽取中：晃动 + 禁点，把 LLM 等待期变成仪式感 */
.fortune-card-back-static.drawing {
  animation: cardDrawing 0.7s ease-in-out infinite;
  cursor: wait;
  pointer-events: none;
}
@keyframes cardDrawing {
  0%, 100% { transform: rotate(0deg) translateY(0); }
  20% { transform: rotate(-2.2deg) translateY(-3px); }
  40% { transform: rotate(2.2deg) translateY(-3px); }
  60% { transform: rotate(-1.6deg) translateY(-2px); }
  80% { transform: rotate(1.6deg) translateY(-2px); }
}

/* ========== 卡面 · 银刻（与卡背同源） ========== */
.face-front {
  background: linear-gradient(160deg, #FBFAF8 0%, #F4F3F0 52%, #EAE8E4 100%);
  transform: rotateY(180deg);
  border: none;
}
.card-border-deco {
  position: absolute;
  inset: 0;
  pointer-events: none;
}
.card-deco-svg {
  width: 100%;
  height: 100%;
  display: block;
}

.card-front-content {
  height: 100%;
  padding: 34px 26px 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
}

/* 身份标签 · 银灰描边胶囊（首枚略深作锚点） */
.card-id-row {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  justify-content: center;
}
.card-id-badge {
  background: transparent;
  border: 1px solid rgba(138,136,132,0.55);
  color: #4A4744;
  font-size: 10px;
  padding: 2px 10px;
  border-radius: 10px;
  font-weight: 500;
  letter-spacing: 0.03em;
}
.card-id-badge.alt {
  background: transparent;
  border-color: rgba(138,136,132,0.32);
  color: #8E8A85;
  font-weight: 400;
}

/* 今日历法 · 农历/节气/黄历宜忌 */
.card-almanac {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 8px 12px;
  border-radius: 6px;
  background: rgba(138,136,132,0.10);
  border: 0.5px dashed rgba(138,136,132,0.45);
}
.almanac-date-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}
.almanac-date {
  font-size: 11px;
  color: #4A4744;
  font-weight: 600;
  letter-spacing: 0.06em;
}
.almanac-term {
  font-size: 10px;
  color: #A8803A;
  font-weight: 600;
  padding: 0 7px;
  border-radius: 8px;
  border: 1px solid rgba(168,128,58,0.5);
  background: rgba(168,128,58,0.10);
}
.almanac-yiji {
  display: flex;
  align-items: baseline;
  gap: 6px;
  justify-content: center;
}
.yiji-label {
  font-size: 10px;
  font-weight: 700;
  color: #3E6B4F;
  width: 16px;
  height: 16px;
  line-height: 16px;
  text-align: center;
  border-radius: 3px;
  background: rgba(62,107,79,0.12);
  flex-shrink: 0;
}
.yiji-label.ji {
  color: #9C4A3C;
  background: rgba(156,74,60,0.12);
}
.yiji-text {
  font-size: 10px;
  color: #6B6864;
  letter-spacing: 0.04em;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 240px;
}

/* 幸运三元素 · 银框 + 暖金数值 */
.card-lucky-row {
  display: flex;
  align-items: stretch;
  gap: 0;
  width: 100%;
  background: rgba(255,255,255,0.5);
  border-radius: 6px;
  padding: 10px 4px;
  border: 0.5px solid rgba(138,136,132,0.45);
}
.lucky-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}
.lucky-label {
  font-size: 9px;
  color: #9A8B6A;
  font-weight: 400;
  letter-spacing: 0.08em;
}
.lucky-value {
  font-size: 15px;
  font-weight: 500;
  color: #A8803A;
}
.lucky-value.food { color: #A8803A; }
.lucky-value.color { color: #A8803A; }
.lucky-value.number { color: #A8803A; font-size: 18px; }
.lucky-divider {
  width: 1px;
  background: rgba(138,136,132,0.3);
  margin: 2px 0;
}

/* 关键词 · 单行不换行，超出裁掉 + 两端渐隐 */
.card-keywords {
  display: flex;
  flex-wrap: nowrap;
  gap: 4px;
  justify-content: center;
  width: 100%;
  overflow: hidden;
  -webkit-mask-image: linear-gradient(90deg, transparent 0, #000 12px, #000 calc(100% - 12px), transparent 100%);
  mask-image: linear-gradient(90deg, transparent 0, #000 12px, #000 calc(100% - 12px), transparent 100%);
}
.keyword-tag {
  flex: 0 0 auto;
  white-space: nowrap;
  background: rgba(138,136,132,0.08);
  color: #57544F;
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 8px;
  border: 1px solid rgba(138,136,132,0.3);
}

/* 建议 · 去符号，改居中文字 + 两侧细线 */
.card-suggestion {
  flex: 1;
  width: 100%;
  background: rgba(255,255,255,0.45);
  border-radius: 6px;
  padding: 14px 16px;
  border: 0.5px solid rgba(138,136,132,0.5);
}
.suggestion-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}
.suggestion-rule {
  flex: 1;
  height: 1px;
  background: rgba(201,169,97,0.45);
}
.suggestion-label {
  font-size: 10px;
  color: #A8803A;
  font-weight: 500;
  letter-spacing: 0.1em;
  white-space: nowrap;
}
.suggestion-text {
  font-size: 12px;
  line-height: 1.7;
  color: #57544F;
  text-align: justify;
}

.card-flip-hint {
  font-size: 10px;
  color: #B0ADA8;
  letter-spacing: 0.08em;
  margin-top: auto;
}

/* ========== AI 对话区 ========== */
.chat-container {
  background: var(--card, #fff);
  border: 1px solid var(--border, #e0e0e0);
  border-radius: 12px;
  padding: 16px;
  min-height: 460px;
}

.chat-messages {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-right: 4px;
  max-height: 320px;
  min-height: 120px;
}

.msg-row {
  display: flex;
  gap: 8px;
  align-items: flex-start;
}
.msg-user { flex-direction: row-reverse; }
.msg-avatar {
  width: 28px; height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  flex-shrink: 0;
}
.avatar-ai { background: rgba(99,102,241,0.1); }
.avatar-user { background: rgba(34,197,94,0.1); }

.msg-bubble {
  max-width: 75%;
  padding: 8px 12px;
  border-radius: 12px;
  font-size: 13px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}
.bubble-ai {
  background: var(--muted, #f5f5f5);
  color: var(--foreground, #333);
  border-bottom-left-radius: 4px;
}
.bubble-user {
  background: #6366f1;
  color: #fff;
  border-bottom-right-radius: 4px;
}
.bubble-ai.thinking {
  display: flex;
  gap: 3px;
  align-items: center;
  padding: 12px 16px;
}

.dot-flashing {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: #999;
  animation: dotFlash 1.4s infinite ease-in-out;
}
.dot-flashing:nth-child(2) { animation-delay: 0.2s; }
.dot-flashing:nth-child(3) { animation-delay: 0.4s; }
@keyframes dotFlash {
  0%, 60%, 100% { opacity: 0.3; }
  30% { opacity: 1; }
}

/* 问题选项 */
.question-area {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border, #e0e0e0);
}
.question-text {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 8px;
  color: var(--foreground, #333);
}
.option-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.option-chip {
  background: var(--card, #fff);
  border: 1px solid var(--border, #d0d0d0);
  color: var(--foreground, #333);
  padding: 6px 14px;
  border-radius: 16px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}
.option-chip:hover {
  border-color: #6366f1;
  background: rgba(99,102,241,0.05);
  color: #6366f1;
}

/* 最终推荐 */
.final-recommend {
  margin-top: 12px;
  padding: 12px;
  border-radius: 10px;
  background: linear-gradient(135deg, rgba(99,102,241,0.06), rgba(99,102,241,0.02));
  border: 1px solid rgba(99,102,241,0.15);
}
.final-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}
.final-icon { font-size: 18px; }
.final-title { font-size: 15px; font-weight: 700; }
.final-reason {
  font-size: 12px;
  color: var(--muted-foreground, #888);
  line-height: 1.6;
  margin-bottom: 8px;
}
.final-alts {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}
.alts-label { font-size: 10px; color: #999; }
.alt-tag {
  background: rgba(99,102,241,0.1);
  color: #6366f1;
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 6px;
}
.final-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}
.delivery-links {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.delivery-link {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 6px 12px;
  border-radius: 8px;
  border: 1px solid hsl(var(--border));
  background: hsl(var(--background));
  text-decoration: none;
  color: hsl(var(--foreground));
  font-size: 12px;
  transition: all 0.15s ease;
}
.delivery-link:hover {
  border-color: hsl(var(--primary));
  background: hsl(var(--primary) / 0.08);
  transform: translateY(-1px);
  box-shadow: 0 2px 8px hsl(var(--primary) / 0.15);
}
.delivery-icon {
  font-size: 18px;
  line-height: 1;
}
.delivery-label {
  font-size: 11px;
  font-weight: 500;
}
.feedback-group {
  display: flex;
  gap: 2px;
  margin-left: auto;
}

/* ========== 流程步骤指示条 ========== */
.step-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 10px 14px;
  background: var(--card, #fff);
  border: 1px solid var(--border, #e0e0e0);
  border-radius: 12px;
}
.step-item {
  display: flex;
  align-items: center;
  gap: 6px;
}
.step-dot {
  width: 22px; height: 22px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
  background: var(--muted, #f0f0f0);
  color: var(--muted-foreground, #999);
  border: 1px solid var(--border, #ddd);
  transition: all 0.3s;
}
.step-label {
  font-size: 12px;
  color: var(--muted-foreground, #999);
  transition: color 0.3s;
}
.step-item.active .step-dot {
  background: #6366f1;
  border-color: #6366f1;
  color: #fff;
  box-shadow: 0 0 0 4px rgba(99,102,241,0.15);
}
.step-item.active .step-label {
  color: #6366f1;
  font-weight: 600;
}
.step-item.done .step-dot {
  background: rgba(99,102,241,0.12);
  border-color: rgba(99,102,241,0.4);
  color: #6366f1;
}
.step-item.done .step-label { color: var(--foreground, #333); }
.step-line {
  width: 40px; height: 1.5px;
  background: var(--border, #ddd);
  transition: background 0.3s;
}
.step-line.done { background: rgba(99,102,241,0.5); }

/* 抽完卡后对话区脉冲引导 */
.chat-nudge {
  animation: chatNudge 2s ease-in-out infinite;
}
@keyframes chatNudge {
  0%, 100% { box-shadow: 0 0 0 0 rgba(99,102,241,0); border-color: var(--border, #e0e0e0); }
  50% { box-shadow: 0 0 0 6px rgba(99,102,241,0.12); border-color: rgba(99,102,241,0.45); }
}

/* 深色模式 */
:root[data-theme="dark"] .chat-container,
.dark .chat-container {
  background: #1e1e1e;
  border-color: #333;
}
:root[data-theme="dark"] .bubble-ai,
.dark .bubble-ai { background: #2a2a2a; color: #ddd; }
:root[data-theme="dark"] .question-text,
.dark .question-text { color: #e0e0e0; }
:root[data-theme="dark"] .option-chip,
.dark .option-chip {
  background: #1e1e1e;
  border-color: #444;
  color: #ccc;
}
:root[data-theme="dark"] .final-recommend,
.dark .final-recommend {
  background: linear-gradient(135deg, rgba(99,102,241,0.1), rgba(99,102,241,0.03));
  border-color: rgba(99,102,241,0.25);
}
:root[data-theme="dark"] .face-back,
.dark .face-back {
  background: #2a2822;
}
:root[data-theme="dark"] .fortune-card-back-static,
.dark .fortune-card-back-static {
  background: #2a2822;
}
:root[data-theme="dark"] .face-front,
.dark .face-front {
  background: linear-gradient(145deg, #2a2520 0%, #252018 50%, #28241c 100%);
  border-color: #4a4030;
}
:root[data-theme="dark"] .suggestion-text,
.dark .suggestion-text { color: #aaa; }
:root[data-theme="dark"] .card-lucky-row,
.dark .card-lucky-row {
  background: rgba(255,255,255,0.05);
  border-color: rgba(200,168,56,0.15);
}
.dark .card-almanac {
  background: rgba(255,255,255,0.05);
  border-color: rgba(200,168,56,0.20);
}
.dark .almanac-date { color: #D6D3CE; }
.dark .almanac-term {
  color: #D9B45C;
  border-color: rgba(217,180,92,0.45);
  background: rgba(217,180,92,0.12);
}
.dark .yiji-text { color: #A8A49E; }
</style>
