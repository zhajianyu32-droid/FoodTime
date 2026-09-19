import { createRouter, createWebHashHistory } from 'vue-router'
import AppLayout from '@/components/AppLayout.vue'
import { TOK } from '@/composables/useApi'
import { reloadMe } from '@/composables/useAuth'

// 标记 reloadMe 是否已完成过（刷新后需要重新加载）
let meReloaded = false

const routes = [
  { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue'), meta: { public: true } },
  { path: '/register', name: 'register', component: () => import('@/views/RegisterView.vue'), meta: { public: true } },
  {
    path: '/',
    component: AppLayout,
    children: [
      { path: 'dashboard', name: 'dashboard', component: () => import('@/views/DashboardView.vue') },
      { path: 'cook', name: 'cook', component: () => import('@/views/CookView.vue') },
      { path: 'order', name: 'order', component: () => import('@/views/OrderView.vue') },
      { path: 'diary', name: 'diary', component: () => import('@/views/DiaryView.vue') },
      { path: 'shopping', name: 'shopping', component: () => import('@/views/ShoppingView.vue') },
      { path: 'ingredients', name: 'ingredients', component: () => import('@/views/IngredientsView.vue') },
      { path: 'settings', name: 'settings', component: () => import('@/views/SettingsView.vue') },
      { path: 'about', name: 'about', component: () => import('@/views/AboutView.vue') },
    ],
  },
  { path: '/', redirect: '/dashboard' },
  { path: '/:pathMatch(.*)*', redirect: '/dashboard' },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

router.beforeEach((to) => {
  if (to.meta.public) return true
  if (!TOK.A) {
    sessionStorage.setItem('ft_redirect', to.fullPath)
    return { name: 'login' }
  }
  return true
})

// 在路由解析前确保 me 已加载，这样子页面 onMounted 执行时 me 有值
// 解决：刷新后 AppLayout.onMounted reloadMe() 还没完成，子页面 loadXxx 因 me=null 静默跳过的问题
router.beforeResolve(async (to) => {
  if (to.meta.public) return true
  if (TOK.A && !meReloaded) {
    await reloadMe()
    meReloaded = true
  }
  return true
})

// 登出时重置，下次登录需要重新加载
router.afterEach(() => {
  if (!TOK.A) meReloaded = false
})

export default router
