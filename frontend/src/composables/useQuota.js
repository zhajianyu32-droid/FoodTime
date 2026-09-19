import { computed } from 'vue'
import { quota } from './useAuth'

const recipeQuotaPercent = computed(() => {
  const total = quota.value.LLM_RECIPES_TOTAL || 100
  const used = quota.value.LLM_RECIPES_QUOTA || 0
  return total > 0 ? Math.round((used / total) * 100) : 0
})

const fortuneQuotaPercent = computed(() => {
  const total = quota.value.LLM_FORTUNE_TOTAL || 10
  const used = quota.value.LLM_FORTUNE_QUOTA || 0
  return total > 0 ? Math.round((used / total) * 100) : 0
})

const chatQuotaPercent = computed(() => {
  const total = quota.value.LLM_CHAT_TOTAL || 50
  const used = quota.value.LLM_CHAT_QUOTA || 0
  return total > 0 ? Math.round((used / total) * 100) : 0
})

export { recipeQuotaPercent, fortuneQuotaPercent, chatQuotaPercent }
