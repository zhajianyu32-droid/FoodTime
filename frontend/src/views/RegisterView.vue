<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { register } from '@/composables/useAuth'
import { showToast } from '@/composables/useToast'

const router = useRouter()

const form = ref({ username: '', password: '', phone: '' })
const loading = ref(false)
const error = ref('')

async function submitRegister() {
  const u = form.value.username.trim()
  const p = form.value.password
  if (u.length < 3 || u.length > 50) {
    error.value = '用户名长度 3-50'
    return
  }
  if (p.length < 6) {
    error.value = '密码至少 6 位'
    return
  }
  loading.value = true
  error.value = ''
  try {
    await register(u, p, form.value.phone.trim())
    showToast('账户创建成功，已自动登录！')
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
        <CardTitle class="text-2xl">注册</CardTitle>
        <CardDescription>创建账户，开始记录你的每一餐</CardDescription>
      </CardHeader>
      <CardContent class="space-y-4">
        <div class="space-y-2">
          <Label for="reg-username">用户名</Label>
          <Input
            id="reg-username"
            v-model="form.username"
            placeholder="3-50位中英数字下划线"
            autocomplete="username"
          />
        </div>
        <div class="space-y-2">
          <Label for="reg-phone">手机号（选填）</Label>
          <Input
            id="reg-phone"
            v-model="form.phone"
            placeholder="可留空"
            autocomplete="tel"
          />
        </div>
        <div class="space-y-2">
          <Label for="reg-password">密码</Label>
          <Input
            id="reg-password"
            type="password"
            v-model="form.password"
            placeholder="至少 6 位"
            autocomplete="new-password"
          />
        </div>
        <p v-if="error" class="text-sm text-destructive">{{ error }}</p>
        <Button class="w-full" :disabled="loading" @click="submitRegister">
          {{ loading ? '注册中…' : '注册' }}
        </Button>
        <p class="text-center text-sm text-muted-foreground">
          已有账户？<router-link to="/login" class="text-primary font-medium hover:underline">返回登录</router-link>
        </p>
      </CardContent>
    </Card>
  </div>
</template>
