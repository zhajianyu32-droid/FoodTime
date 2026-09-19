<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { login } from '@/composables/useAuth'
import { showToast } from '@/composables/useToast'

const router = useRouter()

const form = ref({ username: '', password: '' })
const loading = ref(false)
const error = ref('')

async function submitLogin() {
  if (!form.value.username.trim() || !form.value.password) {
    error.value = '请填写用户名和密码'
    return
  }
  loading.value = true
  error.value = ''
  try {
    const tok = await login(form.value.username, form.value.password)
    form.value.password = ''
    showToast(`欢迎回来, ${tok.user?.username || '用户'}！`)
    router.push('/dashboard')
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center p-4">
    <Card class="w-full max-w-md">
      <CardHeader>
        <CardTitle class="text-2xl">登录</CardTitle>
        <CardDescription>登录食光 FoodTime，开启你的美食决策之旅</CardDescription>
      </CardHeader>
      <CardContent class="space-y-4">
        <div class="space-y-2">
          <Label for="username">用户名</Label>
          <Input
            id="username"
            v-model="form.username"
            placeholder="3-50位中英数字下划线"
            autocomplete="username"
            v-safe-enter="submitLogin"
          />
        </div>
        <div class="space-y-2">
          <Label for="password">密码</Label>
          <Input
            id="password"
            type="password"
            v-model="form.password"
            placeholder="至少 6 位"
            autocomplete="current-password"
            v-safe-enter="submitLogin"
          />
        </div>
        <p v-if="error" class="text-sm text-destructive">{{ error }}</p>
        <Button class="w-full" :disabled="loading" @click="submitLogin">
          {{ loading ? '登录中…' : '登录' }}
        </Button>
        <p class="text-center text-sm text-muted-foreground">
          还没有账户？<router-link to="/register" class="text-primary font-medium hover:underline">立即注册</router-link>
        </p>
      </CardContent>
    </Card>
  </div>
</template>
