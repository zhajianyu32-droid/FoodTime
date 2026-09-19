<script setup>
import { computed, onMounted } from 'vue'
import { useRouter, useRoute, RouterView } from 'vue-router'
import { me, env, quota, reloadMe, logout } from '@/composables/useAuth'
import { showToast } from '@/composables/useToast'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'

const router = useRouter()
const route = useRoute()

// 确保无论从哪个子路由进入，me/quota 都被初始化
onMounted(() => { reloadMe() })

const navGroups = [
  {
    label: '主菜单',
    items: [
      { name: 'cook', path: '/cook', label: 'Cook Mode', icon: '🍳' },
      { name: 'order', path: '/order', label: 'Order Mode', icon: '🛵' },
      { name: 'shopping', path: '/shopping', label: '购物单', icon: '🛒' },
      { name: 'diary', path: '/diary', label: '美食日记', icon: '📖' },
    ],
  },
  {
    label: '管理',
    items: [
      { name: 'ingredients', path: '/ingredients', label: '食材库', icon: '🧊' },
    ],
  },
  {
    label: '系统',
    items: [
      { name: 'settings', path: '/settings', label: '个人设置', icon: '⚙️' },
      { name: 'about', path: '/about', label: '关于', icon: 'ℹ️' },
    ],
  },
]

const currentPath = computed(() => route.path)

function navigate(path) {
  router.push(path)
}

function doLogout() {
  logout()
  showToast('已安全退出登录')
  router.push('/login')
}
</script>

<template>
  <div class="min-h-screen md:h-screen md:flex md:flex-col bg-background md:overflow-hidden">
    <!-- Sidebar -->
    <aside class="fixed inset-y-0 left-0 z-50 w-60 border-r bg-card hidden md:flex md:flex-col">
      <div class="p-4">
        <h1 class="text-lg font-bold">食光 FoodTime</h1>
        <p class="text-xs text-muted-foreground">独居青年吃饭决策助手</p>
      </div>
      <Separator />
      <nav class="flex-1 overflow-y-auto p-3 space-y-6">
        <div v-for="group in navGroups" :key="group.label">
          <p class="mb-2 text-xs font-medium text-muted-foreground">{{ group.label }}</p>
          <div class="space-y-1">
            <button
              v-for="item in group.items"
              :key="item.name"
              class="w-full flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors"
              :class="currentPath === item.path
                ? 'bg-primary text-primary-foreground font-medium'
                : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'"
              @click="navigate(item.path)"
            >
              <span>{{ item.icon }}</span>
              <span>{{ item.label }}</span>
            </button>
          </div>
        </div>
      </nav>
      <Separator />
      <div class="p-3 space-y-2">
        <div class="flex items-center justify-between text-xs">
          <span class="text-muted-foreground">{{ me?.username }}</span>
          <Badge variant="secondary" class="text-xs">{{ env }}</Badge>
        </div>
        <div class="text-xs text-muted-foreground">
          配额 {{ quota.LLM_RECIPES_QUOTA }}/{{ quota.LLM_RECIPES_TOTAL }}
        </div>
        <Button variant="outline" size="sm" class="w-full" @click="doLogout">退出</Button>
      </div>
    </aside>

    <!-- Mobile top bar -->
    <header class="md:hidden sticky top-0 z-50 border-b bg-card px-4 py-3 flex items-center justify-between">
      <span class="font-bold">食光 FoodTime</span>
      <div class="flex items-center gap-2">
        <Badge variant="secondary" class="text-xs">{{ env }}</Badge>
        <Button variant="outline" size="sm" @click="doLogout">退出</Button>
      </div>
    </header>

    <!-- Mobile nav -->
    <nav class="md:hidden sticky top-[57px] z-40 border-b bg-card overflow-x-auto">
      <div class="flex">
        <button
          v-for="item in [...navGroups[0].items, ...navGroups[1].items, ...navGroups[2].items]"
          :key="item.name"
          class="flex-shrink-0 px-3 py-2 text-xs whitespace-nowrap"
          :class="currentPath === item.path
            ? 'text-primary font-medium border-b-2 border-primary'
            : 'text-muted-foreground'"
          @click="navigate(item.path)"
        >
          {{ item.icon }} {{ item.label }}
        </button>
      </div>
    </nav>

    <!-- Main content -->
    <main class="md:pl-60 md:flex-1 md:min-h-0 md:overflow-hidden p-4 md:p-8">
      <div class="max-w-5xl mx-auto md:h-full md:flex md:flex-col md:min-h-0">
        <RouterView />
      </div>
    </main>
  </div>
</template>
